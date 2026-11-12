#!/bin/bash
# veraPDF, the reference PDF/A validator, from its official image: veraPDF's options, and the PDF
# on standard input, so that it sees no file of the host. Without network and with at most 512 MB
# of memory; its exit status and verdict are veraPDF's. The tests run it as HAFLINGER_VERAPDF
# (development guide).
set -euo pipefail

# The image's ID rather than a tag, so that checkouts with different pins don't swap it.
image=$(docker build -q "$(dirname "$0")/../.github/verapdf")
exec docker run -i --rm --network none --memory 512m --read-only --tmpfs /tmp --cap-drop ALL \
  --security-opt no-new-privileges "$image" "$@"
