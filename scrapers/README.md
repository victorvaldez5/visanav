# Scrapers

VisaNav's scrapers crawl official immigration sources and archive the raw pages
(HTML, PDFs, and a JSONL feed of items). There is one Scrapy project,
`uscis_scraper/` (the name is historical), with one spider per source:

| Spider | Source | What it collects |
|---|---|---|
| `uscis` | uscis.gov, uscode.house.gov | USCIS forms, the Immigration and Nationality Act, the USCIS Policy Manual |
| `ecfr` | govinfo.gov bulk data | Current CFR text, one item per section: 8 CFR, 22 CFR Parts 40 to 42 and 62, 20 CFR Parts 655 and 656 |
| `federal-register` | federalregister.gov API | Recent immigration rules, proposed rules, notices and presidential documents |

This guide is for developers who want to add a spider for a **new source** or a
**new country**. Not a developer? You can still help by suggesting a website to
scrape: open an
[**Improve the data**](https://github.com/victorvaldez5/visanav/issues/new?template=improve_data.yml)
issue.

> **Status:** output lands in Cloudflare R2 under `raw/` (or `./output/`
> locally). A source reaches the chatbot's knowledge base once it also has an
> extractor on the API side (see "Wire it into ingestion" below); until then a
> new spider only builds the archive.

## Layout

```
scrapers/uscis_scraper/
├── scrapy.cfg                  # project entrypoint
├── pyproject.toml              # deps (uv workspace member "uscis-scraper")
├── pull_feeds.py               # download crawl feeds from R2 for ingest
└── uscis_scraper/
    ├── settings.py             # env loading, output sinks, pipelines
    ├── items.py                # ScrapedItem (the item schema, shared by every source)
    ├── pipelines.py            # clean, hash-dedupe, save pages, save PDFs
    ├── enumeration.py          # removals for spiders that list their whole source
    ├── health.py               # is a finished crawl trustworthy? (exit code)
    ├── commands/crawl.py       # `scrapy crawl` + the health check
    ├── spiders/
    │   ├── uscis_spider.py             # link-following HTML crawl: copy its patterns
    │   ├── ecfr_spider.py              # bulk XML split into sections, with removals
    │   └── federal_register_spider.py  # JSON API listing, then one request per document
    └── tests/
        ├── test_uscis_spider.py
        ├── test_ecfr_spider.py
        ├── test_federal_register_spider.py
        └── test_pipelines.py
```

## 1. Set up

From the repo root:

```bash
just setup                # once: uv sync --all-packages (+ frontend deps)
just crawl                # sanity check the USCIS spider (local output only)
just crawl ecfr           # or any other spider by name
just test-scraper         # run the scraper tests
```

A local crawl is still a real crawl of the source: it obeys `robots.txt` and
waits 5 seconds between requests, exactly like production (the full USCIS crawl
takes about two hours). While developing a spider, shorten that from
`scrapers/uscis_scraper/` with `scrapy crawl <name> -s DOWNLOAD_DELAY=1`.

`LOCAL_TEST` defaults to `true`, so a local crawl writes to `./output/`
(`items/<spider>/`, `manifests/<spider>.json`, raw pages and PDFs) and needs
**no cloud credentials**. Only the scheduled Railway cron services (one per
spider, `.railway/railway.ts`) run with `LOCAL_TEST=false` and upload to R2.
Settings are read from the shared `config/.env` (see `config/.env.example`).

## 2. Initialize a new spider

Generate a spider inside the existing project (run from `scrapers/uscis_scraper/`):

```bash
scrapy genspider ircc canada.ca
```

This creates `uscis_scraper/spiders/ircc.py`. Any `scrapy.Spider` subclass in
the `spiders/` package is discovered automatically, so there is nothing to
register. Give it:

- a **unique `name`** (it partitions everything: feeds land in
  `raw/items/<name>/`, the incremental manifest is `raw/manifests/<name>.json`,
  raw pages go under `raw/pages/<name>/`, and ingestion uses it as the corpus name),
- `allowed_domains` limited to the official source,
- `start_urls` pointing at index pages that link to the content you want
  (a table of contents or "all forms" page beats crawling a whole site).

## 3. Analyze the HTML source

Before writing parsers, open the target pages and find stable selectors:

1. In your browser, **View Source** or use DevTools to find the element that
   wraps the main content (USCIS uses `#page-content`; the US Code uses
   `#docViewer`). Prefer IDs and semantic class names over layout classes.
2. Find the **links you need to follow** (e.g. USCIS form titles are
   `a.link--form-title`) and any **PDF links**.
3. Test selectors interactively before coding them:

   ```bash
   scrapy shell "https://www.canada.ca/en/immigration-refugees-citizenship.html"
   >>> response.css("main").get()
   >>> response.css("a.some-link::attr(href)").getall()
   ```

4. Check the site's `robots.txt` and terms. Production crawls obey `robots.txt`
   and use a 5-second download delay with autothrottle; keep your spider polite.
   Prefer an official API or bulk download when the source has one (the `ecfr`
   spider reads govinfo's bulk XML because ecfr.gov's `robots.txt` disallows its
   full-text API).

## 4. Extract the relevant parts

Follow the pattern in `uscis_spider.py`: `parse()` routes by URL, sub-parsers
follow links or yield items built with an `ItemLoader`:

```python
import scrapy
from scrapy.loader import ItemLoader
from ..items import ScrapedItem


class IrccSpider(scrapy.Spider):
    name = "ircc"
    allowed_domains = ["canada.ca"]
    start_urls = ["https://www.canada.ca/en/immigration-refugees-citizenship/services.html"]

    def parse(self, response, **kwargs):
        for href in response.css("main a::attr(href)").getall():
            yield response.follow(
                href, callback=self.parse_page, meta={"parent_page": response.url}
            )

    def parse_page(self, response):
        loader = ItemLoader(item=ScrapedItem(), response=response)
        loader.add_value("url", response.url)
        loader.add_value("content_type", "text/html")
        loader.add_value("content", response.css("main").get())
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()
```

Items need `url`, `content_type` (`text/html` or `application/xml`), and
`content` (plus `file_urls` for PDFs, see `parse_pdf` in the USCIS spider). With
those fields, the existing pipelines handle everything else unchanged: cleaning,
content-hash dedupe (unchanged pages are skipped on later crawls via the
spider's own manifest), saving pages, and saving PDFs.

Optional pieces of the contract:

- **`stable_content(self, content)`**: if every fetch of an unchanged page
  differs slightly (a random element id, a "current as of" date, a CSRF token),
  the content hash never matches and the whole site is re-emitted every crawl.
  Define this method to return the content with that markup stripped; only the
  hash uses it, the feed still gets the page as fetched. Check it on two real
  crawls: the second should emit only pages that really changed.
- **`min_items_seen`**: the fewest items (changed or not) a healthy crawl of
  your source sees. After every crawl `scrapy crawl` checks the stats
  (`health.py`) and exits non-zero if the crawl cannot be trusted: nothing
  fetched, most requests failing, a parse error, the feed not stored, or fewer
  items than this. Set it well below a normal crawl so only a real collapse
  trips it.

- **`meta`**: a dict of structured fields the ingest extractor will want and
  that are awkward to recover from the content (a citation, a document type, a
  publication date). It is written to the feed as is.
- **Skipping what you already have**: when the spider opens, the pipeline sets
  `spider.manifest_urls` to every URL the manifest knows. A source whose
  documents never change can skip the request entirely (see
  `federal_register_spider.py`).
- **Removals**: crawls are incremental, so a feed normally only adds or updates
  pages, and a page the source deletes would stay in the knowledge base. Pick
  the mixin in `enumeration.py` that fits how your spider finds pages. A
  **link-following** spider mixes in `MissCountingMixin` (as `uscis` does) and
  needs nothing else: a page is removed once two healthy crawls in a row have
  not seen it, and a crawl that fails its health check counts no misses (a page it does
  see still starts over at zero). Set a
  realistic `min_items_seen` so a blocked crawl is recognised as unhealthy.
  If your spider sees its *whole* source on every crawl, mix in
  `CompleteEnumerationMixin` (`enumeration.py`), call `self.mark_seen(url)` for
  every item and pass `errback=self.mark_failed` on every request. After a
  clean crawl it emits a `removed` line for each URL that has disappeared, and
  ingestion drops it. Do not use this one for a link-following crawl, where a
  missed link would look like a deleted page. Either way, if more than a tenth
  of the known pages would be removed at once the spider assumes the source is
  broken, removes nothing and fails the crawl. Every later crawl then fails the
  same way. If the pages are really gone, run one crawl of that source with
  `-a allow_large_removal=1` (for example
  `scrapy crawl ecfr -a allow_large_removal=1`, or the `allow_large_removal`
  input of the manual `scrape` workflow).

One thing is still USCIS-specific and may need generalizing for a new source:
the PDF filename heuristics in `NamedFilesPipeline.file_path()`
(`pipelines.py`). Flag it in your PR if you touch it.

Run it locally and inspect `./output/`:

```bash
scrapy crawl ircc
```

## 5. Test it

Add `uscis_scraper/tests/test_<name>_spider.py`, mirroring
`test_uscis_spider.py`: build responses from **canned HTML** (no network) and
assert on what each parse method yields.

```python
from scrapy.http import HtmlResponse, Request
from ..spiders.ircc import IrccSpider


def make_html_response(url, body):
    return HtmlResponse(url=url, body=body.encode("utf-8"), encoding="utf-8")


def test_parse_follows_main_links():
    spider = IrccSpider()
    resp = make_html_response(
        "https://www.canada.ca/en/immigration-refugees-citizenship/services.html",
        '<main><a href="/en/a.html">A</a></main>',
    )
    [req] = list(spider.parse(resp))
    assert isinstance(req, Request)
    assert req.callback == spider.parse_page
    assert req.meta["parent_page"] == resp.url
```

CI (the `scraper` job in `.github/workflows/ci.yml`) runs `pytest` on every PR that touches
`scrapers/`.

## 6. Wire it into ingestion

A spider only fills the archive. To make its pages searchable by the assistant,
register the source in `api/knowledge/scrape_utils.py`:

1. Write an extractor `(url, content, meta) -> dict | None` that keeps only the
   substantive text and returns `doc_id`, `title`, `topic`, `instrument` (the
   kind of legal document: `statute`, `regulation`, `agency-guidance`,
   `final-rule`, `proposed-rule`, `notice`, `presidential`, `form`),
   `authority` (the issuing body) and `text`.
2. Add `Source("<spider name>", your_extractor)` to `SOURCES`.
3. Add tests in `api/knowledge/tests.py` that write a feed for your source and
   run the `ingest_scrape` command (see the multi-source tests there).

`just corpus-ingest --dry` then previews the chunks for every source, yours
included. To schedule the crawl, add a cron service for the spider in
`.railway/railway.ts` (a maintainer applies it).

## 7. Open a PR

- Keep one spider (or one source) per PR.
- In the description, list the start URLs, the selectors you chose and why,
  and roughly how many pages a full crawl produces.

Planning something larger, or unsure a source is worth scraping? Open a
[**feature request**](https://github.com/victorvaldez5/visanav/issues/new?template=feature_request.yml)
first so we can agree on scope. See [CONTRIBUTING.md](../CONTRIBUTING.md) for
licensing and conduct.
