#!/bin/bash
# Secrets in the commits: gitleaks over the commits after BASE, or over all of HEAD's without
# one. A BASE this clone doesn't have, as after a force push, is scanned as all of HEAD:
# gitleaks would scan nothing and pass. The same locally and in CI.
set -euo pipefail
cd "$(dirname "$0")/.."

base=${1:-}
range=HEAD
if [ -n "$base" ] && [ "$base" != 0000000000000000000000000000000000000000 ]; then
  if git rev-parse --verify --quiet "$base^{commit}" >/dev/null; then
    range="$base..HEAD"
  else
    echo "::notice::$base isn't in this clone; scanning all commits of HEAD"
  fi
fi
docker build -q -t haflinger-gitleaks .github/gitleaks >/dev/null
docker run --rm -v "$PWD":/repo:ro -w /repo haflinger-gitleaks \
  git --redact --no-banner --log-opts="$range" .
