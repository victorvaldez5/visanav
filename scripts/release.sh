#!/usr/bin/env bash
# Release helper for the develop -> main flow described in docs/RELEASING.md.
#
#   scripts/release.sh check [--local]   what would ship, migrations, new env vars, CI status
#   scripts/release.sh [-y] [--local]    merge origin/develop into main, push, tag vYYYY.MM.DD
#
# `check` exits non-zero if CI on develop's tip is failing or pending. --local runs
# lint + tests locally instead of trusting CI (for when Actions minutes run out).
# The release merges in a throwaway worktree, so your checkout and branches are untouched.
# -y skips the confirmation prompt. Pushing main needs direct-push rights on the branch.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

range="origin/main..origin/develop"

fetch() { git fetch -q origin main develop --tags; }

# Print the migrations in the release, flagging operations that need a human look.
migrations() {
  local files
  files=$(git diff --name-only "origin/main...origin/develop" | grep '/migrations/.*\.py$' | grep -v __init__ || true)
  if [ -z "$files" ]; then echo "none"; return; fi
  while read -r f; do
    flags=$(git show "origin/develop:$f" | grep -oE 'RemoveField|DeleteModel|RunSQL|RunPython|RenameField|RenameModel' | sort -u | paste -sd, - || true)
    if [ -n "$flags" ]; then echo "- $f  (REVIEW: $flags)"; else echo "- $f"; fi
  done <<< "$files"
}

# New variables added to config/.env.example in this release.
new_env_vars() {
  git diff "origin/main...origin/develop" -- config/.env.example \
    | grep -E '^\+[A-Z][A-Z0-9_]*=' | sed 's/^+//; s/=.*//' | sort -u || true
}

# One line per CI workflow on develop's tip; returns 1 if any is not a success.
ci_status() {
  local sha out bad=0
  sha=$(git rev-parse origin/develop)
  out=$(gh run list --commit "$sha" --json name,status,conclusion \
        --jq '.[] | "\(.name)\t\(.status)\t\(.conclusion)"' 2>/dev/null || true)
  if [ -z "$out" ]; then echo "no CI runs found for ${sha:0:7} (path-filtered, or never ran)"; return 1; fi
  while IFS=$'\t' read -r name status conclusion; do
    if [ "$conclusion" = "success" ]; then echo "  ok       $name"
    else echo "  $status${conclusion:+/$conclusion}  $name"; bad=1; fi
  done <<< "$out"
  return $bad
}

summary() {
  echo "## Shipping ($(git rev-list --count --no-merges $range) commits)"
  git log --no-merges --pretty='- %s' "$range"
  echo; echo "## Migrations"; migrations
  echo; echo "## New env vars"
  vars=$(new_env_vars); if [ -n "$vars" ]; then sed 's/^/- /' <<< "$vars"; else echo "none"; fi
}

cmd_check() {
  fetch
  summary; echo; echo "## CI on develop"
  ci_ok=0; ci_status || ci_ok=1
  if [ "${1:-}" = "--local" ]; then
    echo; echo "## Local checks"; just lint && just test
  fi
  echo
  if [ "$ci_ok" = 1 ] && [ "${1:-}" != "--local" ]; then
    echo "NOT READY: CI is not green on develop (re-run it, or use --local)."; exit 1
  fi
  echo "Remember: set new env vars on Railway/Cloudflare/GitHub, and back up Postgres first if a migration is marked REVIEW."
}

cmd_release() {
  local yes=0 local_flag=""
  for a in "$@"; do
    case "$a" in -y|--yes) yes=1 ;; --local) local_flag="--local" ;; *) echo "unknown option: $a"; exit 2 ;; esac
  done

  # Same gate as `check`: prints what ships and exits non-zero if CI isn't green.
  cmd_check $local_flag
  if [ -z "$(git rev-list "$range")" ]; then echo "Nothing to release: main already contains develop."; exit 0; fi

  local tag n=1
  tag="v$(date +%Y.%m.%d)"
  while git rev-parse -q --verify "refs/tags/$tag" >/dev/null; do n=$((n+1)); tag="v$(date +%Y.%m.%d)-$n"; done

  if [ "$yes" != 1 ]; then
    read -r -p "Merge develop into main and tag $tag? This deploys to production. [y/N] " ans
    [ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "aborted"; exit 1; }
  fi

  local wt
  wt=$(mktemp -d)
  trap 'git worktree remove --force "$wt" 2>/dev/null || true' EXIT
  git worktree add -q --detach "$wt" origin/main
  (
    cd "$wt"
    git merge --no-ff -q origin/develop -m "chore(release): $tag" || { echo "merge conflict: resolve develop vs main by hand"; exit 1; }
    git tag -a "$tag" -m "Release $tag"
    git push --atomic origin HEAD:main "refs/tags/$tag"
  )
  git fetch -q origin main --tags
  echo "released $tag: origin/main is now $(git rev-parse --short origin/main). Watch the Railway and Cloudflare deploys."
}

case "${1:-}" in
  check) shift; cmd_check "${1:-}" ;;
  -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' ;;
  *)     cmd_release "$@" ;;
esac
