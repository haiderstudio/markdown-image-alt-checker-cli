#!/usr/bin/env python3
"""Tests for markdown_image_alt_checker. Standard library unittest only."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
EXAMPLES = ROOT / "examples"

sys.path.insert(0, str(SRC))

from markdown_image_alt_checker import (  # noqa: E402
    Image,
    check_file,
    check_images,
    collect_files,
    extract_images,
    run,
)


def write(path, text):
    """Write text to a file, making parent folders as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pass_lines(out):
    """File names the CLI reported as PASS (by file name only)."""
    names = []
    for line in out.splitlines():
        if line.startswith("PASS "):
            names.append(Path(line[5:]).name)
    return names


def fail_lines(out):
    """File names the CLI reported as FAIL (by file name only)."""
    names = []
    for line in out.splitlines():
        if line.startswith("FAIL "):
            names.append(Path(line[5:].split(":")[0]).name)
    return names


class TestExtractImages(unittest.TestCase):
    def test_simple_inline_with_alt(self):
        images = extract_images('![A photo](a.jpg)')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].line, 1)
        self.assertEqual(images[0].src, "a.jpg")
        self.assertEqual(images[0].alt, "A photo")
        self.assertEqual(images[0].text, "![A photo](a.jpg)")

    def test_inline_without_alt(self):
        images = extract_images('![](a.jpg)')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "")

    def test_inline_empty_alt_spaces(self):
        images = extract_images('![   ](a.jpg)')
        self.assertEqual(images[0].alt, "   ")

    def test_inline_with_title(self):
        images = extract_images('![A photo](a.jpg "A title")')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].src, "a.jpg")
        self.assertEqual(images[0].alt, "A photo")

    def test_inline_angle_bracket_src(self):
        images = extract_images('![A photo](<my photo.jpg>)')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].src, "my photo.jpg")

    def test_line_numbers(self):
        text = (
            "# Title\n"
            "\n"
            "![A](a.jpg)\n"
            "![](b.jpg)\n"
            "![C](c.jpg)\n"
        )
        images = extract_images(text)
        self.assertEqual([img.line for img in images], [3, 4, 5])

    def test_reference_style(self):
        images = extract_images('![A photo][team]\n\n[team]: team.jpg\n')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "A photo")
        self.assertEqual(images[0].src, "team")

    def test_collapsed_reference(self):
        images = extract_images('![A photo][]\n')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "A photo")

    def test_shortcut_reference(self):
        images = extract_images('![A photo]\n')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "A photo")

    def test_reference_without_alt(self):
        images = extract_images('![][team]\n')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "")

    def test_image_as_link(self):
        images = extract_images('[![A photo](pic.png)](page.html)\n')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "A photo")
        self.assertEqual(images[0].src, "pic.png")

    def test_image_as_link_without_alt(self):
        images = extract_images('[![](pic.png)](page.html)\n')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "")

    def test_two_images_one_line(self):
        images = extract_images('![A](a.jpg) and ![B](b.jpg)\n')
        self.assertEqual([img.alt for img in images], ["A", "B"])
        self.assertEqual([img.line for img in images], [1, 1])

    def test_no_images(self):
        self.assertEqual(extract_images("# Title\n\nPlain text.\n"), [])

    def test_empty_document(self):
        self.assertEqual(extract_images(""), [])

    def test_plain_link_is_not_an_image(self):
        images = extract_images('[A photo](a.jpg)\n')
        self.assertEqual(images, [])

    def test_escaped_bang_is_not_an_image(self):
        images = extract_images('\\![A photo](a.jpg)\n')
        self.assertEqual(images, [])

    def test_fenced_code_block_skipped(self):
        text = (
            "# Example\n"
            "\n"
            "```\n"
            "![](fake.png)\n"
            "```\n"
            "\n"
            "![Real](real.jpg)\n"
        )
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["real.jpg"])

    def test_tilde_fence_skipped(self):
        text = (
            "~~~\n"
            "![](fake.png)\n"
            "~~~\n"
            "![Real](real.jpg)\n"
        )
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["real.jpg"])

    def test_fence_with_language_skipped(self):
        text = (
            "```markdown\n"
            "![](fake.png)\n"
            "```\n"
        )
        self.assertEqual(extract_images(text), [])

    def test_unclosed_fence_skips_rest(self):
        text = "```\n![](fake.png)\n"
        self.assertEqual(extract_images(text), [])

    def test_inline_code_span_skipped(self):
        text = "Use `![](fake.png)` for an image.\n![Real](real.jpg)\n"
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["real.jpg"])

    def test_double_backtick_span_skipped(self):
        text = "See ``![](fake.png)`` here.\n![Real](real.jpg)\n"
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["real.jpg"])

    def test_html_comment_skipped(self):
        text = (
            "<!-- ![](fake.png) -->\n"
            "![Real](real.jpg)\n"
        )
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["real.jpg"])

    def test_multiline_html_comment_skipped(self):
        text = (
            "<!--\n"
            "![](fake.png)\n"
            "-->\n"
            "![Real](real.jpg)\n"
        )
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["real.jpg"])

    def test_html_img_tag_not_counted(self):
        text = '<img src="a.jpg">\n![Real](real.jpg)\n'
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["real.jpg"])

    def test_reference_definition_not_an_image(self):
        text = "[team]: team.jpg\n"
        self.assertEqual(extract_images(text), [])


class TestCheckImages(unittest.TestCase):
    def test_all_good(self):
        images = [
            Image(1, "a.jpg", "A photo", "![A photo](a.jpg)"),
            Image(2, "b.jpg", "B photo", "![B photo](b.jpg)"),
        ]
        self.assertEqual(check_images(images), [])

    def test_no_images_passes(self):
        self.assertEqual(check_images([]), [])

    def test_missing_alt(self):
        problems = check_images(
            [Image(5, "a.jpg", "", "![](a.jpg)")]
        )
        self.assertEqual(
            problems,
            ["line 5: ![](a.jpg) has no alt text"],
        )

    def test_empty_alt(self):
        problems = check_images(
            [Image(7, "a.jpg", "   ", "![   ](a.jpg)")]
        )
        self.assertEqual(
            problems,
            ["line 7: ![   ](a.jpg) has an empty alt text"],
        )

    def test_whitespace_only_alt_counts_as_empty(self):
        problems = check_images(
            [Image(3, "a.jpg", " ", "![ ](a.jpg)")]
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("empty alt text", problems[0])

    def test_missing_src_still_reports(self):
        problems = check_images([Image(2, "", "", "![]()")])
        self.assertEqual(problems, ["line 2: ![]() has no alt text"])

    def test_reference_style_problem(self):
        problems = check_images(
            [Image(4, "team", "", "![][team]")]
        )
        self.assertEqual(
            problems, ["line 4: ![][team] has no alt text"]
        )

    def test_allow_empty_alt(self):
        images = [Image(7, "a.jpg", "   ", "![   ](a.jpg)")]
        self.assertEqual(check_images(images, allow_empty_alt=True), [])

    def test_allow_empty_alt_still_fails_missing(self):
        images = [Image(7, "a.jpg", "", "![](a.jpg)")]
        problems = check_images(images, allow_empty_alt=True)
        self.assertEqual(len(problems), 1)
        self.assertIn("no alt text", problems[0])

    def test_multiple_problems_in_order(self):
        images = [
            Image(2, "a.jpg", "", "![](a.jpg)"),
            Image(4, "b.jpg", "B photo", "![B photo](b.jpg)"),
            Image(6, "c.jpg", " ", "![ ](c.jpg)"),
        ]
        problems = check_images(images)
        self.assertEqual(len(problems), 2)
        self.assertIn("line 2", problems[0])
        self.assertIn("line 6", problems[1])


class TestCheckFile(unittest.TestCase):
    def test_good_file(self):
        self.assertEqual(check_file(EXAMPLES / "good.md"), [])

    def test_missing_alt_file(self):
        problems = check_file(EXAMPLES / "missing-alt.md")
        self.assertEqual(len(problems), 1)
        self.assertIn("line 4", problems[0])
        self.assertIn("photo.png", problems[0])

    def test_empty_alt_file(self):
        problems = check_file(EXAMPLES / "empty-alt.md")
        self.assertEqual(len(problems), 1)
        self.assertIn("line 4", problems[0])
        self.assertIn("logo.png", problems[0])

    def test_code_block_file_passes(self):
        self.assertEqual(check_file(EXAMPLES / "code-block.md"), [])

    def test_no_images_file_passes(self):
        self.assertEqual(check_file(EXAMPLES / "no-images.md"), [])

    def test_unknown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.txt"
            write(path, "![](a.jpg)")
            problems = check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertIn("unknown file type", problems[0])

    def test_markdown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.markdown"
            write(path, "![A photo](a.jpg)\n")
            self.assertEqual(check_file(path), [])

    def test_missing_file(self):
        problems = check_file(Path("/nonexistent/page.md"))
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot read file", problems[0])

    def test_non_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.md"
            path.write_bytes(b'![A photo](a.jpg)\n\xff\n')
            problems = check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertIn("not valid UTF-8", problems[0])

    def test_bom_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.md"
            path.write_bytes(b'\xef\xbb\xbf![A photo](a.jpg)\n')
            self.assertEqual(check_file(path), [])


class TestCollectFiles(unittest.TestCase):
    def test_single_file(self):
        files, problems = collect_files([str(EXAMPLES / "good.md")])
        self.assertEqual(problems, [])
        self.assertEqual(files, [EXAMPLES / "good.md"])

    def test_directory_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "![A](a.jpg)")
            write(root / "sub" / "b.md", "![B](b.jpg)")
            write(root / "sub" / "c.markdown", "![C](c.jpg)")
            write(root / "sub" / "d.txt", "plain text")
            write(root / "e.html", "<p>not markdown</p>")
            files, problems = collect_files([str(root)])
            self.assertEqual(problems, [])
            self.assertEqual(
                files,
                [root / "a.md", root / "sub" / "b.md",
                 root / "sub" / "c.markdown"],
            )

    def test_directory_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "![A](a.jpg)")
            write(root / "sub" / "b.md", "![B](b.jpg)")
            files, problems = collect_files([str(root)], recursive=False)
            self.assertEqual(problems, [])
            self.assertEqual(files, [root / "a.md"])

    def test_markdown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.markdown", "![A](a.jpg)")
            files, problems = collect_files([str(root)])
            self.assertEqual(problems, [])
            self.assertEqual(files, [root / "a.markdown"])

    def test_missing_path(self):
        files, problems = collect_files(["/nonexistent/page.md"])
        self.assertEqual(files, [])
        self.assertEqual(len(problems), 1)
        self.assertIn("no such file", problems[0])

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            files, problems = collect_files([tmp])
            self.assertEqual(problems, [])
            self.assertEqual(files, [])


class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        code = run(argv, stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def test_good_files_exit_0(self):
        code, out, err = self.run_cli(
            [str(EXAMPLES / "good.md"), str(EXAMPLES / "no-images.md")]
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(pass_lines(out), ["good.md", "no-images.md"])
        self.assertIn("2 file(s) checked, 2 passed, 0 failed", out)

    def test_bad_files_exit_1(self):
        code, out, err = self.run_cli(
            [
                str(EXAMPLES / "good.md"),
                str(EXAMPLES / "missing-alt.md"),
                str(EXAMPLES / "empty-alt.md"),
                str(EXAMPLES / "no-images.md"),
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertIn("4 file(s) checked, 2 passed, 2 failed", out)
        self.assertEqual(
            fail_lines(out), ["missing-alt.md", "empty-alt.md"]
        )

    def test_missing_alt_alone(self):
        code, out, err = self.run_cli([str(EXAMPLES / "missing-alt.md")])
        self.assertEqual(code, 1)
        self.assertIn(
            "line 4: ![](photo.png) has no alt text", out
        )

    def test_empty_alt_alone(self):
        code, out, err = self.run_cli([str(EXAMPLES / "empty-alt.md")])
        self.assertEqual(code, 1)
        self.assertIn(
            "line 4: ![ ](logo.png) has an empty alt text", out,
        )

    def test_code_block_alone_passes(self):
        code, out, err = self.run_cli([str(EXAMPLES / "code-block.md")])
        self.assertEqual(code, 0)
        self.assertEqual(pass_lines(out), ["code-block.md"])

    def test_allow_empty_alt_flag(self):
        code, out, err = self.run_cli(
            ["--allow-empty-alt", str(EXAMPLES / "empty-alt.md")]
        )
        self.assertEqual(code, 0)
        self.assertEqual(pass_lines(out), ["empty-alt.md"])

    def test_allow_empty_alt_still_fails_missing(self):
        code, out, err = self.run_cli(
            ["--allow-empty-alt", str(EXAMPLES / "missing-alt.md")]
        )
        self.assertEqual(code, 1)

    def test_missing_path_exit_2(self):
        code, out, err = self.run_cli(["/nonexistent/page.md"])
        self.assertEqual(code, 2)
        self.assertIn("error: no such file", err)

    def test_no_args_exit_2(self):
        code, out, err = self.run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_bad_flag_exit_2(self):
        code, out, err = self.run_cli(["--no-such-flag", "x.md"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, err = self.run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("markdown_image_alt_checker 1.0.0", out)

    def test_directory_scan(self):
        code, out, err = self.run_cli([str(EXAMPLES)])
        self.assertEqual(code, 1)
        self.assertIn("5 file(s) checked, 3 passed, 2 failed", out)

    def test_files_unchanged_after_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.md"
            text = "![](a.jpg)\n"
            write(path, text)
            code, out, err = self.run_cli([str(path)])
            self.assertEqual(code, 1)
            self.assertEqual(path.read_text(), text)


class TestExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        # The saved output uses relative paths, so run from the repo
        # root, whatever directory the tests were started from.
        old_cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            out = io.StringIO()
            err = io.StringIO()
            code = run(
                [
                    "examples/good.md",
                    "examples/missing-alt.md",
                    "examples/empty-alt.md",
                    "examples/no-images.md",
                ],
                stdout=out,
                stderr=err,
            )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 1)
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertEqual(out.getvalue(), saved)

    def test_run_example_script(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("2 passed, 2 failed", result.stdout)

    def test_readme_quoted_outputs(self):
        readme = (ROOT / "README.md").read_text()
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertIn(saved.strip(), readme)


class TestRepoHygiene(unittest.TestCase):
    def test_stdlib_only_imports(self):
        allowed = {
            "argparse", "contextlib", "io", "os", "re", "subprocess",
            "sys", "tempfile", "unittest", "pathlib",
        }
        for path in list(SRC.rglob("*.py")) + list(
            (ROOT / "tests").rglob("*.py")
        ):
            for line in path.read_text().splitlines():
                if line.startswith("import "):
                    for name in line[7:].split(","):
                        top = name.strip().split(".")[0].split(" ")[0]
                        self.assertIn(
                            top,
                            allowed | {"markdown_image_alt_checker"},
                            "%s in %s" % (top, path),
                        )
                elif line.startswith("from "):
                    top = line.split()[1].split(".")[0]
                    self.assertIn(
                        top,
                        allowed | {"markdown_image_alt_checker"},
                        "%s in %s" % (top, path),
                    )

    def test_no_placeholders_or_secrets(self):
        banned = (
            "TODO",
            "FIXME",
            "lorem",
            "coming soon",
            "API_KEY",
            "api_key",
            "password =",
        )
        # The tests directory is excluded from this scan: the test file
        # itself names the banned words in its own check list, and it
        # uses temp paths. The shipped content is what must be clean.
        # .git is excluded too: GitHub's checkout ships sample hooks
        # under .git/hooks/ that contain "TODO" (Day 21 CI failure).
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            for word in banned:
                self.assertNotIn(word, text, "%s in %s" % (word, path))

    def test_no_absolute_paths(self):
        # Same exclusion as the placeholder scan: the test file itself
        # names temp paths in its own check list.
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            self.assertNotIn(
                "/home/hatch", text, "absolute path in %s" % path
            )
            self.assertNotIn("/tmp/", text, "absolute path in %s" % path)

    def test_gitignore_lists_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_the_tests(self):
        # Substring marker checks only, never an exact comparison
        # with another repo's file: the publish step rewrites ci.yml
        # (Day 65 lesson), so an exact comparison that passes
        # locally fails on the GitHub runner.
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("actions/checkout", ci)
        self.assertIn("actions/setup-python", ci)
        self.assertIn("python3 tests/test_markdown_image_alt_checker.py", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_contains_sample_output(self):
        readme = (ROOT / "README.md").read_text()
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertIn(saved.strip(), readme)


if __name__ == "__main__":
    unittest.main()
