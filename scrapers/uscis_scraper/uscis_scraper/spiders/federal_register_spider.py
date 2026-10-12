import datetime as dt
import re
from urllib.parse import urlencode

import scrapy

from ..items import ScrapedItem


class FederalRegisterSpider(scrapy.Spider):
    """Recent immigration-relevant Federal Register documents, one item per document.

    Uses the Federal Register public API (no key). Listing queries select the
    documents; each new document's full text is then fetched as HTML. Published
    documents never change, so one already in the manifest is skipped before its
    body is requested.
    """

    name = "federal-register"
    allowed_domains = ["federalregister.gov"]
    custom_settings = {"USER_AGENT": "visanav-scraper (+https://github.com/victorvaldez5)"}

    API_URL = "https://www.federalregister.gov/api/v1/documents.json"
    # How far back to look, by publication date: `-a retention_days=30` overrides.
    # Ingest applies its own window, so an old notice ages out of the corpus too.
    RETENTION_DAYS = 730

    # Selection rules. A document is taken if any one rule matches; widen here.
    # 1. Everything these agencies publish (API agency slugs).
    AGENCIES = (
        "u-s-citizenship-and-immigration-services",
        "executive-office-for-immigration-review",
    )
    # 2. Anything that cites these CFR titles (title, part; None is any part).
    CFR_REFERENCES = ((8, None), (22, 40), (22, 41), (22, 42))
    # 3. Presidential documents whose full text matches one of these terms.
    PRESIDENTIAL_TERMS = ("immigration", "nonimmigrant", "refugee", "asylum")
    # Paperwork Reduction Act notices (form-burden comment requests) are most of
    # what USCIS publishes and tell an applicant nothing.
    EXCLUDED_TITLES = re.compile(r"information collection|approved collection|comment request", re.I)

    FIELDS = (
        "document_number", "title", "type", "publication_date", "effective_on",
        "html_url", "body_html_url", "agencies", "cfr_references",
    )

    def __init__(self, retention_days=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retention_days = int(retention_days or self.RETENTION_DAYS)
        self._queued = set()

    def listing_urls(self, today=None):
        since = (today or dt.date.today()) - dt.timedelta(days=self.retention_days)
        queries = [[("conditions[agencies][]", slug) for slug in self.AGENCIES]]
        for title, part in self.CFR_REFERENCES:
            query = [("conditions[cfr][title]", title)]
            if part is not None:
                query.append(("conditions[cfr][part]", part))
            queries.append(query)
        for term in self.PRESIDENTIAL_TERMS:
            queries.append([("conditions[type][]", "PRESDOCU"), ("conditions[term]", term)])

        common = [
            ("per_page", 200),
            ("order", "newest"),
            ("conditions[publication_date][gte]", since.isoformat()),
            *(("fields[]", field) for field in self.FIELDS),
        ]
        return [f"{self.API_URL}?{urlencode(query + common)}" for query in queries]

    async def start(self):
        for url in self.listing_urls():
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        data = response.json()
        # ContentHashPipeline publishes the manifest's URLs when the spider opens.
        known = getattr(self, "manifest_urls", frozenset())
        for doc in data.get("results") or []:
            number = doc.get("document_number")
            url = doc.get("html_url")
            body_url = doc.get("body_html_url")
            if not number or not url or not body_url:
                continue
            # The selection rules overlap, so the same document recurs across listings.
            if number in self._queued or url in known:
                continue
            if self.EXCLUDED_TITLES.search(doc.get("title") or ""):
                continue
            self._queued.add(number)
            yield scrapy.Request(body_url, callback=self.parse_document, cb_kwargs={"doc": doc})

        if data.get("next_page_url"):
            yield scrapy.Request(data["next_page_url"], callback=self.parse_listing)

    def parse_document(self, response, doc):
        yield ScrapedItem(
            url=doc["html_url"],
            content_type="text/html",
            content=response.text,
            meta={
                "document_number": doc["document_number"],
                "title": doc.get("title"),
                "type": doc.get("type"),
                "publication_date": doc.get("publication_date"),
                "effective_on": doc.get("effective_on"),
                "agencies": [a["name"] for a in doc.get("agencies") or [] if a.get("name")],
                "cfr_references": [
                    {"title": ref.get("title"), "part": ref.get("part")}
                    for ref in doc.get("cfr_references") or []
                ],
            },
        )
