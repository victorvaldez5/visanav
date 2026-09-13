# Contributing data

You do **not** need to be a programmer to contribute. If you know an immigration
system — as a lawyer, paralegal, accredited representative, law student, advocate,
or someone who has been through it — you can add knowledge or resources by
editing text files. Thank you: this is the work that makes the tool actually
help people.

## What you can contribute

- **Knowledge** — plain-language explanations of a process, category, form, or
  fee, grounded in an official source.
- **Resources** — organizations that help people (legal aid, pro-bono clinics,
  accredited nonprofits).
- **A whole new country** — the biggest and most valuable contribution.

## The golden rules

1. **Cite your source.** Every document and every organization needs a real
   `source_url`.
2. **Prefer official sources.** If you mark something `source_type: official`,
   the link must be to an official government domain for that country (listed in
   the country's `meta.yaml`). Validation will reject it otherwise.
3. **No case-specific legal advice.** Describe the *general* process. The
   assistant always reminds users it is not a lawyer — the data should read the
   same way.
4. **Summarize, don't paste.** Write facts in your own words and link the source.
5. **Date it.** Set `last_verified` to the day you checked the source.

## Add a knowledge document

1. Find `countries/<code>/knowledge/` (create `<code>/` from `_template/` if the
   country doesn't exist yet — see below).
2. Copy `_template/knowledge/TEMPLATE.md` into a topic subfolder, e.g.
   `countries/us/knowledge/citizenship/naturalization-basics.md`.
3. Fill in the frontmatter (see [schema/vocabularies.md](schema/vocabularies.md)
   for allowed `topic` and other values) and write the body in Markdown.

## Add a resource (organization)

1. Open (or create) a file under `countries/<code>/resources/` —
   `national.yaml` for country-wide orgs, or `by-region/<region>.yaml`.
2. Add a list entry following `_template/resources/TEMPLATE.yaml`. Only
   `org_id`, `name`, `org_type`, `country`, `source_url`, and `last_verified`
   are required, but fill in as much as you can.

## Add a new country

1. Copy the `_template/` folder to `countries/<code>/`, where `<code>` is the
   lowercase [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
   code (e.g. `ca`, `mx`, `de`, `ph`).
2. Edit `meta.yaml`: set `country` to the uppercase code, list the real
   immigration authorities and their **official domains**, and add yourself to
   `maintainers`.
3. Add at least one knowledge doc or resource so the folder isn't empty.

## Before you open a pull request

Run the validator locally (optional — CI runs it too):

```bash
pip install -r data/scripts/requirements.txt
python data/scripts/validate.py
```

Fix anything it flags, then open a PR. A country maintainer will review the
substance (are the facts right? is the source good?) and merge. Once merged, the
knowledge is ingested into the assistant's corpus.

Questions or want to become a maintainer for a country? Open an issue.
