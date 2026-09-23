# Immigration data

This directory is the heart of **VisaNav**: an open, community-curated dataset of
immigration information and help resources, organized by country. The chat
assistant is only as trustworthy as what lives here, so this is the most
valuable place to contribute, and **no coding is required**. If you know an
immigration system as a lawyer, paralegal, accredited representative, law
student, advocate, or someone who has been through it, you can help.

There are two kinds of data:

| Kind | What it is | Format | Feeds |
|------|------------|--------|-------|
| **Knowledge** | How immigration works: processes, categories, forms, fees | Markdown + YAML frontmatter | the assistant's retrieval corpus |
| **Resources** | Where to get help: legal aid, pro-bono orgs, clinics | YAML lists | the org directory |

Not ready to edit files? Open an
[**Improve the data**](https://github.com/victorvaldez5/visanav/issues/new?template=improve_data.yml)
issue to suggest a website, report wrong information, or volunteer as a reviewer.

## The rules

1. **Cite your source.** Every knowledge doc and resource entry needs a real
   `source_url`.
2. **Prefer official sources.** Anything marked `source_type: official` must link
   to a domain listed in that country's `meta.yaml` (e.g. `uscis.gov` for the
   US). Validation rejects it otherwise.
3. **No case-specific legal advice.** Describe the *general* process. The
   assistant always reminds users it is not a lawyer, and the data should read
   the same way.
4. **Summarize, don't paste.** Write facts in your own words and link the source.
   Government facts aren't copyrightable, but a source's wording can be.
5. **Date it.** Set `last_verified` to the day you checked the source.

Automated validation checks the *format*; a country maintainer checks the
*truth*.

## Layout

```
data/
  schema/            JSON Schemas + controlled vocabularies (vocabularies.md)
  scripts/           validate.py (CI gate) and ingest.py (chunk preview)
  countries/
    _template/       copy this to start a new country
    us/              worked example
      meta.yaml      authorities, official domains, maintainers
      knowledge/     .md documents, grouped by topic
      resources/     .yaml org lists (national.yaml + by-region/)
```

A country is a self-contained folder: adding Germany means adding files under
`countries/de/` and nothing else. You never touch application code.

## How to contribute

**Add a knowledge document.** Copy `_template/knowledge/TEMPLATE.md` into a topic
subfolder, e.g. `countries/us/knowledge/citizenship/naturalization-basics.md`.
Fill in the frontmatter (allowed values like `topic` are in
[schema/vocabularies.md](schema/vocabularies.md)) and write the body in Markdown.

**Add a resource (organization).** Add an entry to `countries/<code>/resources/national.yaml`
for country-wide orgs, or `by-region/<region>.yaml`, following
`_template/resources/TEMPLATE.yaml`. Only `org_id`, `name`, `org_type`,
`country`, `source_url`, and `last_verified` are required, but fill in as much as
you can.

**Add a new country.** Copy `_template/` to `countries/<code>/`, where `<code>` is
the lowercase [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
code (e.g. `ca`, `mx`, `ph`). In `meta.yaml`, set `country` to the uppercase code,
list the real immigration authorities and their **official domains**, and add
yourself to `maintainers`. Then add at least one knowledge doc or resource.

**Check your work, then open a pull request.** CI runs the validator too, but
running it first saves a round trip:

```bash
pip install -r data/scripts/requirements.txt
python data/scripts/validate.py        # everything (or: validate.py us)
python data/scripts/ingest.py us       # preview the chunks that would be built
```

A country maintainer reviews the substance and merges. Want to become a
maintainer for a country? Say so in an issue.

## Building the corpus (maintainers)

Embedding and loading into the vector store happens in the API, not here:

```bash
cd api && python manage.py ingest us --upsert   # needs VOYAGE_API_KEY + a database
```

## Licensing

Everything in `data/` is licensed under
[Creative Commons Attribution 4.0 (CC-BY-4.0)](LICENSE), so anyone can reuse it
with attribution. By contributing data you agree it is published under those
terms, so only submit information you are permitted to share. The application
code is licensed separately under AGPL-3.0 (see the root [LICENSE](../LICENSE)).
