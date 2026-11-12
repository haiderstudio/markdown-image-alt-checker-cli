# markdown-image-alt-checker-cli

Check every Markdown image has alt text, fail CI on missing or empty alt.

[![CI](https://github.com/haiderstudio/markdown-image-alt-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/markdown-image-alt-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`markdown_image_alt_checker` reads local Markdown files and checks one rule
per image:

- **Every Markdown image must have alt text, and the alt text must not be
  empty.** An image written as `![](photo.png)` fails, and one written as
  `![ ](logo.png)` (only spaces) fails too.

- It prints `PASS` or `FAIL` per file, with the exact line of each problem
  and the image itself, and a summary line. It exits 1 when any file fails,
  so it can fail a CI run.
- It checks one file, several files, or a whole directory (directories are
  scanned for `.md` and `.markdown` files, including subdirectories, unless
  you pass `--no-recursive`).
- Both image forms are checked: inline images `![alt](src)` and
  reference-style images `![alt][ref]`, `![alt][]`, and the shortcut form
  `![alt]`.
- `--allow-empty-alt` allows an alt text made of spaces only, for images
  that are decorative on purpose. An image with no alt text at all still
  fails.
- It is report-only and runs fully offline: it never rewrites a file, sends
  nothing anywhere, and needs no key.
- Images inside fenced code blocks (``` or ~~~), inline code spans, and
  HTML comments are not counted, because they are examples of the syntax,
  not real images. An escaped `\![alt](src)` is literal text, not an image,
  and is not counted either.

## What it does NOT do

- It does not judge whether the alt text is good. `![image](photo.png)`
  passes; only a missing or empty alt fails. Writing good alt text is the
  author's job.
- It does not make an exception for decorative images on its own. An empty
  alt is reported unless you pass `--allow-empty-alt`.
- It does not check `<img>` tags in HTML files. That is the job of
  [image-alt-checker-cli](https://github.com/haiderstudio/image-alt-checker-cli)
  (repo #30 in this series), which checks alt text on `<img>` tags in HTML
  files and says plainly that it does not check images in Markdown files.
  This tool is the Markdown half of that job.
- It does not check whether a reference-style image has a matching
  definition (`[ref]: url`), or whether the image file itself exists. Those
  are other tools' jobs.
- It does not check links, headings, or anything else about the page. Those
  are other tools' jobs.
- It does not fix a file. A missing alt is reported, not repaired.
- It does not fetch a live site. Only files on your own machine.

## Who it is for

Anyone who keeps Markdown files that need every image described before a
build: a docs site where a missing alt makes an image invisible to a screen
reader, a blog where every post image needs alt text, or a team adding a CI
step that fails the build when a page ships with an image that has no alt.
If the files are right, you get a quiet pass; if one is wrong, the report
says exactly which file, which line, and which image.

## How this differs from similar tools

The quoted GitHub search for the exact name,
`"markdown-image-alt-checker-cli"`, returns 0 results. The unquoted search
`markdown image alt checker` returns 2 results, both from the same author:
ruthtxh/markdown-image-alt-text-checker (0 stars) — "A markdown image alt-text
checker with optional Microsoft Azure Cognitive Services (Computer Vision)
integration for suggestions" — and ruthtxh/markdown-image-alt-text-checker-test
(0 stars), the same author's test repo. No rival is a tested CLI with a CI
gate, and the one tool that does the exact job puts its headline feature
behind a paid Azure key.

This tool does a narrower job: a Python standard-library-only CLI that checks
one thing — every Markdown image has alt text — on one file or a whole folder
of local Markdown, reports the exact line per failure, and exits 1 for CI.
No install beyond Python, no cloud, no key, no network, no fixing.

## Install

Python standard library only — no packages to download. Clone the repo and
run it in place:

```sh
git clone https://github.com/haiderstudio/markdown-image-alt-checker-cli.git
cd markdown-image-alt-checker-cli
```

Python 3.10 or newer.

## Usage

Check the example files:

```sh
python3 src/markdown_image_alt_checker.py examples/good.md examples/missing-alt.md examples/empty-alt.md examples/no-images.md
```

Real output:

```text
PASS examples/good.md
FAIL examples/missing-alt.md: line 4: ![](photo.png) has no alt text
FAIL examples/empty-alt.md: line 4: ![ ](logo.png) has an empty alt text
PASS examples/no-images.md
4 file(s) checked, 2 passed, 2 failed
```

The command exits 1, because two files fail. The same output is saved in
`examples/sample-output.txt`.

Check the good files alone:

```sh
python3 src/markdown_image_alt_checker.py examples/good.md examples/no-images.md
```

Real output:

```text
PASS examples/good.md
PASS examples/no-images.md
2 file(s) checked, 2 passed, 0 failed
```

The command exits 0.

Check a whole folder:

```sh
python3 src/markdown_image_alt_checker.py docs/
```

Directories are scanned for `.md` and `.markdown` files, including
subdirectories. Add `--no-recursive` to stay in the top folder only.

## Examples

### 1. An image with no alt text fails CI

`examples/missing-alt.md` has an image with no alt text at all:

```sh
python3 src/markdown_image_alt_checker.py examples/missing-alt.md
```

```text
FAIL examples/missing-alt.md: line 4: ![](photo.png) has no alt text
1 file(s) checked, 0 passed, 1 failed
```

The exit code is 1. Put the same command in CI and the build fails until
the alt text is added. With the alt text added the same command prints
`PASS examples/missing-alt.md` and exits 0.

### 2. An empty alt text fails too

`examples/empty-alt.md` has an image with an alt text of one space:

```sh
python3 src/markdown_image_alt_checker.py examples/empty-alt.md
```

```text
FAIL examples/empty-alt.md: line 4: ![ ](logo.png) has an empty alt text
1 file(s) checked, 0 passed, 1 failed
```

If the image is decorative on purpose, pass `--allow-empty-alt` and the
same file passes:

```sh
python3 src/markdown_image_alt_checker.py --allow-empty-alt examples/empty-alt.md
```

```text
PASS examples/empty-alt.md
1 file(s) checked, 1 passed, 0 failed
```

An image with no alt text at all still fails with that flag — only a
spaces-only alt is allowed.

### 3. An image inside a code block is not a real image

`examples/code-block.md` shows the `![](...)` syntax inside a fenced code
block, and one real image below it:

```sh
python3 src/markdown_image_alt_checker.py examples/code-block.md
```

```text
PASS examples/code-block.md
1 file(s) checked, 1 passed, 0 failed
```

The image in the code block is an example of the syntax, so it is skipped;
the real image has alt text, so the file passes.

## How it is tested

```sh
python3 -m unittest discover -s tests
```

75 tests, standard library `unittest` only. They cover image extraction
(line numbers, titles, angle-bracket sources, reference-style, collapsed and
shortcut references, images used as links, plain links, escaped images,
fenced code blocks skipped, inline code spans skipped, HTML comments
skipped, `<img>` tags not counted), the alt rule (missing, empty,
whitespace-only, `--allow-empty-alt`), file checks (good and bad files,
unknown extension, `.markdown` extension, missing file, non-UTF-8, BOM),
directory collection (recursive, `--no-recursive`, `.markdown`), the command
line (exit codes 0, 1 and 2, `--version`, bad flags, files unchanged after a
run), the bundled examples, and the repo hygiene checks (standard-library
imports only, no placeholder text, no secrets, no absolute paths). The
tests pass from any working directory, not only from the repo root.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Small, focused improvements are
welcome. Run the tests before opening a pull request.

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea — a small checker
for one Markdown image-alt rule — follows the same pattern as the other
single-job tools in this series; no code was copied from any other project.
The one existing tool that does the exact job,
ruthtxh/markdown-image-alt-text-checker, was only read about in the research
notes; nothing was taken from it.
