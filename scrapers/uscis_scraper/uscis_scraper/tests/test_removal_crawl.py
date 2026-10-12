"""Page removals through a real crawl: `scrapy crawl`, the idle signal, the
pipelines, the feed export and the crawl's exit status, end to end.

The other removal tests drive the spider and the hash pipeline by hand. These
run the project's own `scrapy crawl` in a subprocess against a small site of
local files, with a link-following spider like `uscis` (MissCountingMixin).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT = Path(__file__).resolve().parents[2]  # where scrapy.cfg lives

_SPIDER = '''
import scrapy

from uscis_scraper.enumeration import MissCountingMixin
from uscis_scraper.items import ScrapedItem


class SiteSpider(MissCountingMixin, scrapy.Spider):
    name = "site"
    min_items_seen = 5

    def __init__(self, listing=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with open(listing, encoding="utf-8") as f:
            self.start_urls = f.read().split()

    def parse(self, response, **kwargs):
        yield ScrapedItem(url=response.url, content_type="text/html", content=response.text)
'''


class _Site:
    """Twelve pages on disk, and the output directory of the crawls over them."""

    def __init__(self, tmp_path):
        self.root, self.out, self.crawls = tmp_path, tmp_path / "output", 0
        (tmp_path / "site_spiders").mkdir()
        (tmp_path / "site_spiders" / "__init__.py").write_text(_SPIDER, encoding="utf-8")
        self.urls = []
        for n in range(12):
            page = tmp_path / "pages" / f"page-{n}.html"
            page.parent.mkdir(exist_ok=True)
            page.write_text(f"<p>page {n}, same every week</p>", encoding="utf-8")
            self.urls.append(page.as_uri())

    def crawl(self, urls, *args):
        """One `scrapy crawl` over the pages still linked. Returns the exit
        status and the feed's lines."""
        self.crawls += 1
        listing = self.root / "listing.txt"
        listing.write_text("\n".join(urls), encoding="utf-8")
        feed = self.out / "items" / "site" / f"{self.crawls}.jsonl"
        settings = {
            "SPIDER_MODULES": "site_spiders",
            "LOCAL_FILES": self.out,
            "FILES_STORE": self.out,
            "FEED_URI": feed,
            # Local files: nothing to be polite to.
            "ROBOTSTXT_OBEY": False,
            "DOWNLOAD_DELAY": 0,
            "AUTOTHROTTLE_ENABLED": False,
        }
        command = [sys.executable, "-m", "scrapy", "crawl", "site", "-a", f"listing={listing}", *args]
        for name, value in settings.items():
            command += ["-s", f"{name}={value}"]
        done = subprocess.run(
            command, cwd=_PROJECT, capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONPATH": str(self.root), "LOCAL_TEST": "true"},
        )
        lines = []
        if feed.exists():
            lines = [json.loads(line) for line in feed.read_text(encoding="utf-8").splitlines()]
        return done.returncode, lines

    def manifest(self):
        return json.loads((self.out / "manifests" / "site.json").read_text(encoding="utf-8"))


@pytest.fixture
def site(tmp_path):
    return _Site(tmp_path)


def test_a_page_that_stays_away_is_removed_through_the_feed(site):
    gone, rest = site.urls[0], site.urls[1:]

    status, lines = site.crawl(site.urls)
    assert status == 0 and sorted(line["url"] for line in lines) == sorted(site.urls)

    # First absence: nothing is emitted at all (the other pages are unchanged).
    status, lines = site.crawl(rest)
    assert (status, lines) == (0, [])
    assert site.manifest()[gone]["missed"] == 1

    # Second absence: the idle spider puts a `removed` line in the feed, and
    # the page is forgotten only now that the feed holds it.
    status, lines = site.crawl(rest)
    assert status == 0
    assert [(line["url"], line["removed"]) for line in lines] == [(gone, True)]
    assert gone not in site.manifest() and len(site.manifest()) == 11


def test_a_refused_removal_fails_the_crawl_until_it_is_allowed(site):
    gone, rest = site.urls[:5], site.urls[5:]
    assert site.crawl(site.urls)[0] == 0
    assert site.crawl(rest) == (0, [])  # five pages missed once: plausible so far

    # Five of twelve would go at once: past the cap. Nothing is removed and the
    # crawl exits non-zero, which is what shows it as failed on Railway.
    status, lines = site.crawl(rest)
    assert status != 0 and lines == []
    assert all(site.manifest()[url]["missed"] == 1 for url in gone)

    # A person checked that the pages are really gone.
    status, lines = site.crawl(rest, "-a", "allow_large_removal=1")
    assert status == 0
    assert sorted(line["url"] for line in lines) == sorted(gone)
    assert all(line["removed"] for line in lines)
    assert sorted(site.manifest()) == sorted(rest)
