#!/bin/bash
# phax's converter en16931-cii2ubl, from the image of .github/cii2ubl: every XML file in INVOICES,
# in one call, each turned from CII into UBL as <name>-ubl.xml in OUTPUT. Without network, the
# invoices read-only, with at most 512 MB of memory; it exits with 0 even where it refuses a file.
# The conformance tests run it as HAFLINGER_CII2UBL (development guide).
set -euo pipefail

if [ $# -ne 2 ] || [ ! -d "$1" ] || [ ! -d "$2" ]; then
  echo "usage: cii2ubl.sh INVOICES OUTPUT" >&2
  exit 2
fi
invoices=$(realpath "$1")
output=$(realpath "$2")
shopt -s nullglob
files=()
for file in "$invoices"/*.xml; do
  files+=("/invoices/${file##*/}")
done
if [ ${#files[@]} -eq 0 ]; then
  echo "cii2ubl.sh: no XML file in $1" >&2
  exit 2
fi
# The image's ID rather than a tag, so that checkouts with different pins don't swap it.
image=$(docker build -q "$(dirname "$0")/../.github/cii2ubl")
exec docker run --rm --network none --memory 512m --read-only --tmpfs /tmp:exec --cap-drop ALL \
  --security-opt no-new-privileges --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$invoices,target=/invoices,readonly" \
  --mount "type=bind,source=$output,target=/output" \
  "$image" -t /output "${files[@]}"
