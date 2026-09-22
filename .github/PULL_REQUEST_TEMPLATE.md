<!--
Thanks for contributing to VisaNav!
Use a Conventional Commit-style title, e.g. "feat(frontend): add language switcher".
-->

## What does this PR do?

<!-- A short description of the change and why. -->

## Related issue

<!-- e.g. Closes #123 -->

## Type of change

- [ ] Data (immigration knowledge or resources under `data/`)
- [ ] Bug fix
- [ ] New feature
- [ ] Docs
- [ ] Refactor / chore

## Checklist

- [ ] My commits are signed off (`git commit -s`) per the [DCO](https://developercertificate.org/).
- [ ] The PR title follows Conventional Commits (`type(scope): summary`).
- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md) and agree to the applicable license (AGPL-3.0 for code, CC-BY-4.0 for data).

### For code changes

- [ ] Tests and linters pass locally for the service(s) I touched
      (`pytest` / `ruff` for the API, `npm run lint` + `npm run build` for the frontend).

### For data changes

- [ ] `python data/scripts/validate.py` passes.
- [ ] Every claim cites a real `source_url`; anything `source_type: official`
      links a domain listed in the country's `meta.yaml`.
- [ ] `last_verified` is set to the date I checked the source.
- [ ] No case-specific legal advice; facts are summarized, not pasted.
