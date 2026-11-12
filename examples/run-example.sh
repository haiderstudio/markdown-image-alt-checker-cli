#!/bin/sh
# Run the checker over the example files and show the result.
# The checker exits 1 (two files fail), so the script keeps going
# and exits 0 either way.
set -e
cd "$(dirname "$0")/.."
python3 src/markdown_image_alt_checker.py examples/good.md examples/missing-alt.md examples/empty-alt.md examples/no-images.md || true
