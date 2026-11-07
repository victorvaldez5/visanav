# Matt Pocock skills

Project-scoped Cursor skills. They are copied into `.agents/skills/` and committed. Nothing was installed into a user directory (`~/.cursor/skills/`, `~/.agents/skills/`) or into a Grok Bot skill library. Putting these files in the repo does not make them available in Grok Bot chat.

## Provenance

- Source: <https://github.com/mattpocock/skills>
- Commit: `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` (2026-10-31, `software-factory: glossary skill for designing a factory (#1316)`)
- Installer: `npx skills@latest` (skills CLI 1.7.6 when installed), agent `cursor`, method `copy`
- Lock: `skills-lock.json` records each skill's content hash. It does not record the git commit. The commit above is the revision these copies were taken from.
- License: MIT, Copyright (c) 2026 Matt Pocock. The notice is `.agents/skills/LICENSE`.

`grilling` is the only productivity skill included. `grill-with-docs` is a one-line caller of `grilling` and `domain-modeling`, so those two are installed with it. `codebase-design` is installed because `tdd` calls it when a seam's shape is still open.

## What was configured

The setup skill's choices were already settled in this repo, so they were recorded rather than re-asked:

- Issue tracker: GitHub Issues (`docs/agents/issue-tracker.md`). The `git remote` is GitHub. Pull requests are not a triage surface.
- Triage labels: the five defaults already mapped in `docs/agents/triage-labels.md`, and already present on the repo (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). This change did not create labels.
- Domain docs: single-context, root `GLOSSARY.md` plus `docs/adr/`, created lazily. No `CONTEXT.md` existed to rename. The consumer doc now uses the upstream `GLOSSARY.md` name. `i18n/GLOSSARY.md` stays the translation glossary.

`CLAUDE.md` already had an `## Agent skills` section, so that section was updated in place. `AGENTS.md` was not created: the setup skill edits `CLAUDE.md` when that file exists, and an unmerged pull request (#51) uses a root `AGENTS.md` for the `develop` / `just release` loop. This change does not edit `AGENTS.md` or `CONTRIBUTING.md`. If both land, they do not overlap.

## Reinstall this revision

From the repo root. `DISABLE_TELEMETRY=1` skips the installer's usage report. Do not pass `-g`, and do not pass any agent other than `cursor`.

```bash
DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 npx skills@latest add \
  mattpocock/skills@4ae2317ddb22b046e26455e4f9c9b3aaaf62212d \
  --full-depth --copy -a cursor -y \
  --skill setup-matt-pocock-skills \
  --skill grill-with-docs \
  --skill grilling \
  --skill domain-modeling \
  --skill codebase-design \
  --skill to-spec \
  --skill to-tickets \
  --skill tdd \
  --skill code-review \
  --skill diagnosing-bugs \
  --skill triage
```

## Update later

`npx skills update -p -y` follows `skills-lock.json` to the latest `mattpocock/skills` main branch. It is not pinned to the commit above. Review the diff before committing, and do not pass `-g`.

## Not installed

The rest of the upstream catalog, including `implement`, `implement-spec`, `wayfinder`, `improve-codebase-architecture`, `ask-matt`, `pr`, and the productivity skills other than `grilling`. `docs/agents/issue-tracker.md` still contains the upstream wayfinding section because that is the GitHub tracker template. The `wayfinder` skill itself is not installed, and `wayfinder:*` labels were not created.

`diagnosing-bugs/scripts/hitl-loop.template.sh` is a copy-and-edit prompt. It waits for someone at a terminal. It was not run.

## Still open

- Whether the four services should be separate domain contexts. The existing doc and the setup skill's default are single-context. That was kept.
- Whether to add a root domain `GLOSSARY.md` now. The skills create it lazily, so none was added.
- Whether to install `implement`, `wayfinder`, or `improve-codebase-architecture` later.
