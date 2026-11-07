#!/usr/bin/env bash
# Cases for scripts/check_pr_base.sh. No GitHub calls and no git writes.
# Covers a pull request into main (must fail), a pull request into develop
# (must pass), and a push (must pass, including when a base ref is present,
# which is how just release updates main).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
check="$root/scripts/check_pr_base.sh"

run_case() {
  local expect="$1" event="$2" base="$3" label="$4"
  local code=0
  local err
  err="$(mktemp)"
  GITHUB_EVENT_NAME="$event" GITHUB_BASE_REF="$base" bash "$check" >/dev/null 2>"$err" || code=$?
  if [ "$code" -ne "$expect" ]; then
    echo "FAIL $label: expected exit $expect, got $code" >&2
    cat "$err" >&2
    rm -f "$err"
    exit 1
  fi
  if [ "$expect" -eq 1 ] && ! grep -q "just release" "$err"; then
    echo "FAIL $label: failure did not mention just release" >&2
    cat "$err" >&2
    rm -f "$err"
    exit 1
  fi
  rm -f "$err"
  echo "ok $label"
}

run_case 1 pull_request main "PR into main fails"
run_case 1 pull_request refs/heads/main "PR into refs/heads/main fails"
run_case 0 pull_request develop "PR into develop passes"
run_case 0 pull_request "" "PR with an empty base passes"
run_case 0 pull_request feature/anything "PR into another branch passes"
run_case 0 push "" "push with no base ref passes"
run_case 0 push main "push passes even if a base ref is main"
run_case 0 "" main "a missing event does not fail"

echo "all pull-request base guard cases passed"
