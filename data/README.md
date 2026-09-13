# Immigration data

This directory is the heart of **immigration-ai**: an open, community-curated
dataset of immigration information and help resources, organized by country. The
chat assistant is only as trustworthy as what lives here, so this data is the
project's most valuable asset — and the easiest, highest-impact place to
contribute, **no coding required**.

There are two kinds of data:

| Kind | What it is | Format | Feeds |
|------|------------|--------|-------|
| **Knowledge** | How immigration works — processes, categories, forms, fees | Markdown + YAML frontmatter | the assistant's retrieval corpus (vector store) |
| **Resources** | Where to get help — legal aid, pro-bono orgs, clinics | YAML lists | the org directory |

## Layout

```
data/
  schema/            canonical JSON Schemas + controlled vocabularies
  scripts/           validate.py (CI gate) and ingest.py (build the corpus)
  countries/
    _template/       copy this to start a new country
    us/              worked example
      meta.yaml      authorities + official domains + maintainers
      knowledge/     .md documents, grouped by topic
      resources/     .yaml org lists (national.yaml + by-region/)
```

A **country is a self-contained folder**. Adding one — say `de/` for Germany —
means adding files under `countries/de/`, nothing else. You never touch the
application code.

## The rules that keep it trustworthy

1. Every knowledge doc and resource entry **cites a `source_url`**.
2. Anything marked `source_type: official` **must** cite a domain declared in
   that country's `meta.yaml` (e.g. `uscis.gov` for the US). This is enforced
   automatically.
3. Everything carries a `last_verified` date.
4. Automated validation gates *format*; a country maintainer gates *truth*.

## Working with the data

```bash
pip install -r data/scripts/requirements.txt

python data/scripts/validate.py            # validate everything (CI runs this)
python data/scripts/validate.py us         # just one country
python data/scripts/ingest.py us           # dry-run: see the chunks that would be built
```

To contribute, read [CONTRIBUTING-data.md](CONTRIBUTING-data.md).

## Licensing of the data

Code in this repository is licensed under AGPL-3.0 (see the root `LICENSE`).
When you contribute data, only submit information you are permitted to
redistribute, and cite where it came from. Government facts (form numbers,
official processes) are not themselves copyrightable, but a specific source's
*expression* can be — summarize and cite rather than copying at length.
