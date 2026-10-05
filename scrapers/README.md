# Scrapers

VisaNav's scrapers crawl official immigration sources and archive the raw pages
(HTML, PDFs, and a JSONL feed of items). Today there is one Scrapy project,
`uscis_scraper/`, with one spider (`uscis`) that crawls USCIS forms, the
Immigration and Nationality Act, and the USCIS Policy Manual.

This guide is for developers who want to add a spider for a **new source** or a
**new country**. Not a developer? You can still help by suggesting a website to
scrape: open an
[**Improve the data**](https://github.com/victorvaldez5/visanav/issues/new?template=improve_data.yml)
issue.

> **Status:** scraping is raw archival. Output lands in Cloudflare R2 under
> `raw/` (or `./output/` locally) and is **not yet wired into the chatbot's
> knowledge base**. The assistant currently answers from the hand-curated
> `data/` corpus. New spiders still matter: they build the archive that future
> ingestion will draw from.

## Layout

```
scrapers/uscis_scraper/
├── scrapy.cfg                  # project entrypoint
├── pyproject.toml              # deps (uv workspace member "uscis-scraper")
├── pull_feeds.py               # download crawl feeds from R2 for ingest
└── uscis_scraper/
    ├── settings.py             # env loading, output sinks, pipelines
    ├── items.py                # UscisItem (the item schema)
    ├── pipelines.py            # clean, hash-dedupe, save HTML, save PDFs
    ├── spiders/
    │   └── uscis_spider.py     # the existing spider: copy its patterns
    └── tests/
        ├── test_uscis_spider.py
        └── test_pipelines.py
```

## 1. Set up

From the repo root:

```bash
just setup                # once: uv sync --all-packages (+ frontend deps)
just crawl                # sanity check the existing spider (local output only)
just test-scraper         # run the scraper tests
```

`LOCAL_TEST` defaults to `true`, so a local crawl writes to `./output/`
(`html/`, `items/`, PDFs, and `manifest.json`) and needs **no cloud
credentials**. Only the weekly GitHub Actions job
(`.github/workflows/scrape.yml`) runs with `LOCAL_TEST=false` and uploads to R2.
Settings are read from the shared `config/.env` (see `config/.env.example`).

## 2. Initialize a new spider

Generate a spider inside the existing project (run from `scrapers/uscis_scraper/`):

```bash
scrapy genspider ircc canada.ca
```

This creates `uscis_scraper/spiders/ircc.py`. Any `scrapy.Spider` subclass in
the `spiders/` package is discovered automatically, so there is nothing to
register. Give it:

- a **unique `name`** (it partitions output: items land in `raw/items/<name>/`),
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

## 4. Extract the relevant parts

Follow the pattern in `uscis_spider.py`: `parse()` routes by URL, sub-parsers
follow links or yield items built with an `ItemLoader`:

```python
import scrapy
from scrapy.loader import ItemLoader
from ..items import UscisItem


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
        loader = ItemLoader(item=UscisItem(), response=response)
        loader.add_value("url", response.url)
        loader.add_value("content_type", "text/html")
        loader.add_value("content", response.css("main").get())
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()
```

Items need `url`, `content_type`, and `content` (plus `file_urls` for PDFs, see
`parse_pdf` in the USCIS spider). With those fields, the existing pipelines
handle everything else unchanged: cleaning, content-hash dedupe (unchanged pages
are skipped on later crawls via `manifest.json`), saving HTML, and saving PDFs.

Two things are still USCIS-specific and may need generalizing for a new source:
the PDF filename heuristics in `NamedFilesPipeline.file_path()`
(`pipelines.py`), and the item class name (`UscisItem`, which is generic in
practice). Flag either in your PR if you touch them.

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

## 6. Open a PR

- Keep one spider (or one source) per PR.
- In the description, list the start URLs, the selectors you chose and why,
  and roughly how many pages a full crawl produces.

Planning something larger, or unsure a source is worth scraping? Open a
[**feature request**](https://github.com/victorvaldez5/visanav/issues/new?template=feature_request.yml)
first so we can agree on scope. See [CONTRIBUTING.md](../CONTRIBUTING.md) for
licensing and conduct.
