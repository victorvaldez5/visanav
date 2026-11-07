#!/usr/bin/env bash
# Fail this run when it is a pull request into main.
#
# main is production. just release updates it with a push, not a pull request
# (docs/RELEASING.md, scripts/release.sh). This script must stay a no-op for
# every push, including that one. GitHub sets GITHUB_BASE_REF only for
# pull_request events; the event name is what decides, so a stray base ref
# on a push cannot fail the release.
#
# GITHUB_EVENT_NAME and GITHUB_BASE_REF are the Actions defaults. Callers
# (and scripts/test_check_pr_base.sh) may set them.
set -euo pipefail

event="${GITHUB_EVENT_NAME:-}"
base="${GITHUB_BASE_REF:-}"
# Actions sets the short name. Accept the full ref too, in case a caller
# passes what github.ref uses.
base="${base#refs/heads/}"

if [ "$event" = "pull_request" ] && [ "$base" = "main" ]; then
  echo "Pull requests merge into develop. main is updated only by just release (docs/RELEASING.md)." >&2
  exit 1
fi

echo "pull request base ok (event=${event:-<unset>} base=${base:-<unset>})"
