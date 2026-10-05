#!/usr/bin/env bash
# Release helper for the develop -> main flow described in docs/RELEASING.md.
#
#   scripts/release.sh check [--local]   what would ship, migrations, new env vars, CI status
#   scripts/release.sh pr                open the develop -> main PR with a generated body
#   scripts/release.sh tag               after merging, tag origin/main as vYYYY.MM.DD
#
# `check` exits non-zero if CI on develop's tip is failing or pending. --local runs
# lint + tests locally instead of trusting CI (for when Actions minutes run out).
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

cmd_pr() {
  fetch
  local body title
  title="chore(release): $(date +%Y-%m-%d)"
  body="$(summary)

## Before merging
- [ ] CI green on develop
- [ ] New env vars set
- [ ] Postgres backup taken if any migration is destructive
- [ ] Any manual data step noted here

After merging: \`scripts/release.sh tag\`. See docs/RELEASING.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
  gh pr create --base main --head develop --title "$title" --body "$body"
}

cmd_tag() {
  fetch
  local tag="v$(date +%Y.%m.%d)"
  if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then echo "tag $tag already exists"; exit 1; fi
  git tag -a "$tag" -m "Release $tag" origin/main
  git push origin "$tag"
  echo "tagged origin/main as $tag"
}

case "${1:-}" in
  check) shift; cmd_check "${1:-}" ;;
  pr)    cmd_pr ;;
  tag)   cmd_tag ;;
  *)     sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
