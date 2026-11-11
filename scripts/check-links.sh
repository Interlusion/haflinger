#!/bin/bash
# Markdown links: relative Markdown links only (no Obsidian wiki-links, which
# GitHub shows as text), absolute ones into this repository in the README, which
# PyPI shows too, and every local link and #anchor resolves.
set -euo pipefail
cd "$(dirname "$0")/.."

# Tracked files only, so a local run matches CI.
md() { git ls-files -z '*.md' | xargs -0 -r "$@"; }

# [[target]] or [[target|text]] outside code; `[[ -f x ]]` in shell has a space. A code block
# opens with three or more backticks or tildes, also in a blockquote, and closes with at least
# as many of the same character on a line of their own; code spans of one or two backticks.
wiki=$(md awk '
  FNR == 1 { fence = "" }
  {
    line = $0
    sub(/^[ \t]*(>[ \t]*)*/, "", line)
    if (match(line, /^(`+|~+)/) && RLENGTH >= 3) {
      run = substr(line, 1, RLENGTH); rest = substr(line, RLENGTH + 1)
      if (fence == "" && !(run ~ /^`/ && index(rest, "`"))) { fence = run; next }
      if (fence != "" && substr(run, 1, 1) == substr(fence, 1, 1) && length(run) >= length(fence) && rest ~ /^[ \t]*$/) { fence = ""; next }
    }
    if (fence != "") next
    gsub(/``([^`]|`[^`])*``/, "", line)
    gsub(/`[^`]*`/, "", line)
    if (line ~ /\[\[[^] []/) print FILENAME ":" FNR ": " $0
  }
')
if [ -n "$wiki" ]; then
  echo "$wiki"
  echo "::error::Obsidian wiki-links above; use relative Markdown links: [text](path.md)"
  exit 1
fi
docker build -q -t haflinger-lychee .github/lychee >/dev/null
# The links of the README and the changelog, as lychee parses them (inline, reference and HTML
# links, not code), without the remap below: none may resolve to a local file, an #anchor
# included, as PyPI shows the README and the GitHub Release a changelog section (ADR-013), and
# none of the README's into this repository may name a tag, which only a release's build writes.
for file in README.md CHANGELOG.md; do
  relative=$(docker run --rm -v "$PWD":/w:ro -w /w haflinger-lychee --config /dev/null --dump "$file" | grep '^file://' || true)
  if [ -n "$relative" ]; then
    echo "$relative"
    echo "::error::$file links above are relative, which break on PyPI and in a GitHub Release; link https://github.com/Interlusion/haflinger/blob/main/<path>"
    exit 1
  fi
done
links=$(docker run --rm -v "$PWD":/w:ro -w /w haflinger-lychee --config /dev/null --dump README.md)
tagged=$(grep -E '^https://github\.com/Interlusion/haflinger/(blob|tree)/v[0-9]' <<<"$links" || true)
if [ -n "$tagged" ]; then
  echo "$tagged"
  echo "::error::README.md links above name a tag; on main they link https://github.com/Interlusion/haflinger/blob/main/<path>"
  exit 1
fi
md docker run --rm -v "$PWD":/w:ro -w /w haflinger-lychee --config lychee.toml --no-progress
