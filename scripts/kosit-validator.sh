#!/bin/bash
# KoSIT's validator with KoSIT's XRechnung configuration, from the image of
# .github/kosit-validator: every XML file in INVOICES, in one call, with one report per file,
# <name>-report.xml, written into REPORTS. Without network, the invoices read-only, with at most
# 1 GB of memory; its exit status is the validator's, the number of rejected files. The
# conformance tests run it as HAFLINGER_KOSIT_VALIDATOR (development guide).
set -euo pipefail

if [ $# -ne 2 ] || [ ! -d "$1" ] || [ ! -d "$2" ]; then
  echo "usage: kosit-validator.sh INVOICES REPORTS" >&2
  exit 2
fi
invoices=$(realpath "$1")
reports=$(realpath "$2")
shopt -s nullglob
files=()
for file in "$invoices"/*.xml; do
  files+=("/invoices/${file##*/}")
done
if [ ${#files[@]} -eq 0 ]; then
  echo "kosit-validator.sh: no XML file in $1" >&2
  exit 2
fi
# The image's ID rather than a tag, so that checkouts with different pins don't swap it.
image=$(docker build -q "$(dirname "$0")/../.github/kosit-validator")
exec docker run --rm --network none --memory 1g --read-only --tmpfs /tmp:exec --cap-drop ALL \
  --security-opt no-new-privileges --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$invoices,target=/invoices,readonly" \
  --mount "type=bind,source=$reports,target=/reports" \
  "$image" -o /reports "${files[@]}"
