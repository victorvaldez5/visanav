import re

import scrapy

from scrapy.loader import ItemLoader
from ..items import ScrapedItem

# Markup that differs on every fetch of an otherwise unchanged page: Drupal
# stamps each embedded view with a random id, every Policy Manual chapter shows
# the date the whole manual is current as of (uscis.gov), and every U.S. Code
# page carries the date its text is current through (uscode.house.gov).
_VOLATILE_MARKUP = re.compile(
    r"js-view-dom-id-[0-9a-f]+"
    r'|<span class="current-date__value">.*?</span>'
    r'|<span class="lawsInEffect">.*?</span>',
    re.S,
)


class UscisSpider(scrapy.Spider):
    name = "uscis"
    allowed_domains = ["uscis.gov", "uscode.house.gov"]
    start_urls = [
        "https://www.uscis.gov/forms/all-forms",
        # 'https://www.uscis.gov/forms/filing-guidance',
        # 'https://www.uscis.gov/downloading-and-printing-immigration-forms',
        # 'https://www.uscis.gov/topics',
        # 'https://www.uscis.gov/green-card',
        # # 'https://www.uscis.gov/citizenship',
        # 'https://www.uscis.gov/laws',
        # The Policy Manual TOC links every chapter directly (one hop to ~456
        # chapter pages), so seed it rather than the volume index.
        "https://www.uscis.gov/policy-manual/table-of-contents",
        "https://www.uscis.gov/laws-and-policy/legislation/immigration-and-nationality-act",
        # 'https://www.uscis.gov/tools',
        # add other entry points as needed
    ]

    # A full crawl sees about 730 pages and 250 PDFs; far fewer means the site
    # blocked us or its markup changed (see health.py).
    min_items_seen = 500

    def stable_content(self, content):
        """What ContentHashPipeline hashes to decide whether a page changed."""
        return _VOLATILE_MARKUP.sub("", content)

    def parse(self, response, **kwargs):
        # Route to different parsers by URL pattern
        if "/forms/all-forms" in response.url:
            yield from self.parse_all_forms(response)

        if "legislation" in response.url:
            yield from self.parse_legislation_page(response)

        if "/policy-manual" in response.url:
            yield from self.parse_policy_manual(response)

    def parse_all_forms(self, response):
        # Target links like <a href="/ar-11" class="link link--form-title">
        form_links = response.css("a.link--form-title::attr(href)").getall()
        for href in form_links:
            yield response.follow(
                href, callback=self.parse_forms_page, meta={"parent_page": response.url}
            )

    def parse_forms_page(self, response, **kwargs):
        # Yield an item for the HTML page itself
        loader = ItemLoader(item=ScrapedItem(), response=response)
        pdf_links = response.css("article.media a::attr(href)").getall()
        loader.add_value("url", response.url)
        loader.add_value("content_type", "text/html")
        loader.add_value("content", response.css("#page-content").get())
        loader.add_value("files", pdf_links)
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()

        # Follow all links; PDFs go to parse_pdf, other pages recurse
        for href in pdf_links:
            if href.endswith(".pdf"):
                yield response.follow(
                    href, callback=self.parse_pdf, meta={"parent_page": response.url}
                )

    def parse_legislation_page(self, response, **kwargs):
        us_code_links = response.css("td > a::attr(href)").getall()
        for href in us_code_links:
            yield response.follow(
                href,
                callback=self.parse_uscode_page,
                meta={"parent_page": response.url},
            )

    def parse_uscode_page(self, response, **kwargs):
        loader = ItemLoader(item=ScrapedItem(), response=response)
        loader.add_value("url", response.url)
        loader.add_value("content_type", "text/html")
        loader.add_value("content", response.css("#docViewer").get())
        loader.add_value("files", [])
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()

    def parse_policy_manual(self, response, **kwargs):
        # The Table of Contents links every chapter directly; follow each to
        # parse_policy_chapter. Duplicate links across the page are collapsed by
        # the default dupe filter.
        chapter_links = response.css('a[href*="-chapter-"]::attr(href)').getall()
        for href in chapter_links:
            yield response.follow(
                href,
                callback=self.parse_policy_chapter,
                meta={"parent_page": response.url},
            )

    def parse_policy_chapter(self, response, **kwargs):
        # Chapter bodies use the same #page-content container as form pages.
        # These are HTML-only; the per-volume "Download PDF" links are skipped
        # as redundant with the chapter HTML.
        loader = ItemLoader(item=ScrapedItem(), response=response)
        loader.add_value("url", response.url)
        loader.add_value("content_type", "text/html")
        loader.add_value("content", response.css("#page-content").get())
        loader.add_value("files", [])
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()

    def parse_pdf(self, response):
        loader = ItemLoader(item=ScrapedItem(), response=response)
        loader.add_value("url", response.url)
        loader.add_value("content_type", "application/pdf")
        loader.add_value("file_urls", [response.url])
        loader.add_value("files", [response.url])
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()
