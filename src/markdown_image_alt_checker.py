#!/usr/bin/env python3
"""Check Markdown images carry alt text, fail CI on a missing alt.

Run: python3 src/markdown_image_alt_checker.py docs/
     python3 src/markdown_image_alt_checker.py post.md

The tool reads local Markdown files and checks one rule: every
Markdown image ``![alt](src)`` must have alt text, and the alt
text must not be empty. Every problem names the file and the exact
line it is on. The tool exits 1 when any file fails, so it can
fail a CI run.

It is report-only: it never rewrites a file, and it runs fully
offline. It sends nothing anywhere and needs no key.

Both image forms are checked: inline images ``![alt](src)`` and
reference-style images ``![alt][ref]``, ``![alt][]`` and the
shortcut form ``![alt]``. Images inside fenced code blocks, inline
code spans, and HTML comments are not counted, because they are
examples of the syntax, not real images. An escaped ``\\![alt]``
is literal text, not an image, and is not counted either.

HTML ``<img>`` tags in a Markdown file are NOT checked here: that
is the job of image-alt-checker-cli (repo #30 in this series),
which checks alt text on ``<img>`` tags in HTML files. This tool
is the Markdown half of that job.

Exit codes: 0 when every file passes, 1 when any file fails,
2 for a usage or input problem (missing file, bad flag, no files).
"""

import argparse
import contextlib
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

MD_EXTS = {".md", ".markdown"}

_IMAGE_RE = re.compile(
    r"(?<!\\)!\[([^\]]*)\]"
    r"(?:\((?:<[^>]+>|[^)]*)\)|\[([^\]]*)\])?"
)
_CODE_SPAN_RE = re.compile(r"(`+)(.*?)\1")
_FENCE_RE = re.compile(r"^ {0,3}(```|~~~)")


class Image:
    """One Markdown image: its line, its destination, its alt text."""

    def __init__(self, line, src, alt, text):
        self.line = line
        self.src = src
        self.alt = alt
        self.text = text

    def __repr__(self):
        return "Image(line %d, src=%r, alt=%r)" % (
            self.line,
            self.src,
            self.alt,
        )


def _strip_code_spans(line):
    """Remove inline code spans (text between backticks) from a line."""
    return _CODE_SPAN_RE.sub("", line)


def _strip_html_comments(line, in_comment):
    """Remove HTML comment spans from a line.

    Returns (cleaned line, in_comment) where in_comment says whether
    a comment opened on this line is still open at the end of it.
    """
    while True:
        if in_comment:
            end = line.find("-->")
            if end == -1:
                return "", True
            line = line[end + 3:]
            in_comment = False
            continue
        start = line.find("<!--")
        if start == -1:
            return line, False
        end = line.find("-->", start + 4)
        if end == -1:
            return line[:start], True
        line = line[:start] + line[end + 3:]


def _destination(match):
    """The image destination: the paren target, or the ref label."""
    whole = match.group(0)
    alt_end = whole.find("]") + 1
    rest = whole[alt_end:]
    if rest.startswith("("):
        inner = rest[1:-1].strip()
        if inner.startswith("<"):
            return inner[1:inner.find(">")]
        return inner.split()[0] if inner.split() else ""
    if rest.startswith("["):
        return rest[1:-1]
    return ""


def extract_images(text):
    """Return the list of Markdown images in one document.

    Images inside fenced code blocks, inline code spans, and HTML
    comments are skipped. Line numbers are the lines the ``![``
    starts on.
    """
    images = []
    in_fence = None
    in_comment = False
    for number, raw_line in enumerate(text.splitlines(), start=1):
        fence = _FENCE_RE.match(raw_line)
        if in_fence is not None:
            if fence and fence.group(1) == in_fence:
                in_fence = None
            continue
        if fence:
            in_fence = fence.group(1)
            continue
        line, in_comment = _strip_html_comments(raw_line, in_comment)
        if in_comment and line == "":
            continue
        line = _strip_code_spans(line)
        for match in _IMAGE_RE.finditer(line):
            alt = match.group(1)
            if alt.startswith("["):
                alt = alt[1:]
            images.append(
                Image(number, _destination(match), alt, match.group(0))
            )
    return images


def check_images(images, allow_empty_alt=False):
    """Check one list of images. Returns a list of problem strings."""
    problems = []
    for image in images:
        if image.alt == "":
            problems.append(
                "line %d: %s has no alt text" % (image.line, image.text)
            )
        elif image.alt.strip() == "" and not allow_empty_alt:
            problems.append(
                "line %d: %s has an empty alt text"
                % (image.line, image.text)
            )
    return problems


def check_file(path, allow_empty_alt=False):
    """Check one file. Returns a list of problem strings (empty = pass)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return ["cannot read file: %s" % exc]
    except UnicodeDecodeError:
        return ["file is not valid UTF-8 text"]
    suffix = path.suffix.lower()
    if suffix not in MD_EXTS:
        return ["unknown file type (use .md or .markdown)"]
    return check_images(extract_images(text), allow_empty_alt)


def collect_files(paths, recursive=True):
    """Expand paths into a sorted list of Markdown files.

    A path may be a file or a directory. Directories are scanned for
    ``.md`` and ``.markdown`` files, recursively when ``recursive``
    is true. Returns (files, problems) where problems are usage
    errors.
    """
    files = []
    problems = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            problems.append("no such file or directory: %s" % raw)
            continue
        if path.is_file():
            files.append(path)
            continue
        if recursive:
            found = []
            for ext in (".md", ".markdown"):
                found.extend(path.rglob("*" + ext))
        else:
            found = []
            for ext in (".md", ".markdown"):
                found.extend(path.glob("*" + ext))
        files.extend(sorted(set(found)))
    return files, problems


def build_parser():
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="markdown_image_alt_checker",
        description=(
            "Check Markdown image alt text in local files: every "
            "![alt](src) must have alt text, and the alt text must "
            "not be empty. Prints PASS or FAIL per file and exits 1 "
            "when any file fails, so it can fail a CI run."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="Markdown file or directory to check. Directories are "
        "scanned for .md and .markdown files.",
    )
    parser.add_argument(
        "--allow-empty-alt",
        action="store_true",
        help="Allow an empty alt text (alt with only spaces). For "
        "images that are decorative on purpose. An image with no "
        "alt text at all still fails.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not look inside subdirectories of a named directory.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="markdown_image_alt_checker " + VERSION,
    )
    return parser


def run(argv=None, stdout=None, stderr=None):
    """Run the checker. Returns the exit code (0, 1, or 2)."""
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    try:
        # argparse writes --version output and usage errors to the real
        # sys.stdout/sys.stderr, so point those at the caller's streams.
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    files, problems = collect_files(args.paths, recursive=not args.no_recursive)
    if problems:
        for problem in problems:
            print("error: %s" % problem, file=err)
        return 2
    if not files:
        print("error: no Markdown files found", file=err)
        return 2
    passed = 0
    failed = 0
    for path in files:
        found = check_file(path, args.allow_empty_alt)
        if found:
            failed += 1
            print("FAIL %s: %s" % (path, "; ".join(found)), file=out)
        else:
            passed += 1
            print("PASS %s" % path, file=out)
    print(
        "%d file(s) checked, %d passed, %d failed"
        % (passed + failed, passed, failed),
        file=out,
    )
    return 1 if failed else 0


def main():
    """Entry point for the command line."""
    sys.exit(run())


if __name__ == "__main__":
    main()
