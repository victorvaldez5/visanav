import datetime as dt
import json
from urllib.parse import parse_qs, urlparse

import pytest
from scrapy.http import HtmlResponse, TextResponse

from ..spiders.federal_register_spider import FederalRegisterSpider


@pytest.fixture
def spider():
    return FederalRegisterSpider()


def _doc(number, title="Extension of the Designation of Honduras for Temporary Protected Status",
         doc_type="Notice", **extra):
    return {
        "document_number": number,
        "title": title,
        "type": doc_type,
        "publication_date": "2026-09-29",
        "effective_on": None,
        "html_url": f"https://www.federalregister.gov/documents/2026/09/29/{number}/slug",
        "body_html_url": f"https://www.federalregister.gov/documents/full_text/html/2026/09/29/{number}.html",
        "agencies": [
            {"name": "Homeland Security Department", "slug": "homeland-security-department"},
            {"name": "U.S. Citizenship and Immigration Services"},
        ],
        "cfr_references": [{"title": 8, "part": "244", "chapter": None, "citation_url": None}],
        **extra,
    }


def _listing(results, next_page_url=None):
    payload = {"count": len(results), "results": results}
    if next_page_url:
        payload["next_page_url"] = next_page_url
    return TextResponse(
        url=FederalRegisterSpider.API_URL,
        body=json.dumps(payload).encode("utf-8"),
        encoding="utf-8",
    )


def test_listing_urls_cover_every_selection_rule_within_the_window(spider):
    queries = [
        parse_qs(urlparse(url).query) for url in spider.listing_urls(today=dt.date(2026, 10, 12))
    ]

    # Every query is limited to the retention window (730 days by default).
    assert all(q["conditions[publication_date][gte]"] == ["2024-10-12"] for q in queries)

    assert {
        "u-s-citizenship-and-immigration-services",
        "executive-office-for-immigration-review",
    } == set(queries[0]["conditions[agencies][]"])
    cfr = [
        (q["conditions[cfr][title]"][0], q.get("conditions[cfr][part]", [None])[0])
        for q in queries
        if "conditions[cfr][title]" in q
    ]
    assert cfr == [("8", None), ("22", "40"), ("22", "41"), ("22", "42")]
    presidential = [q for q in queries if q.get("conditions[type][]") == ["PRESDOCU"]]
    assert [q["conditions[term]"][0] for q in presidential] == list(spider.PRESIDENTIAL_TERMS)


def test_retention_window_is_a_spider_argument():
    spider = FederalRegisterSpider(retention_days="30")
    (first, *_) = spider.listing_urls(today=dt.date(2026, 10, 12))
    assert parse_qs(urlparse(first).query)["conditions[publication_date][gte]"] == ["2026-09-12"]


def test_parse_listing_requests_each_new_document_body_once(spider):
    known = _doc("2026-00001")
    spider.manifest_urls = frozenset({known["html_url"]})
    results = [
        _doc("2026-00002"),
        _doc("2026-00002"),  # the same document matched by another rule
        known,  # ingested by an earlier crawl; published documents never change
        _doc(
            "2026-00003",
            title="Agency Information Collection Activities; Extension, Without Change, "
            "of a Currently Approved Collection: Application To Replace Permanent Resident Card",
        ),
        _doc("2026-00004", body_html_url=None),  # no full text published
    ]
    out = list(spider.parse_listing(_listing(results, next_page_url="https://www.federalregister.gov/api/v1/documents.json?page=2")))

    body, next_page = out
    assert body.url.endswith("/2026-00002.html")
    assert body.callback == spider.parse_document
    assert body.cb_kwargs["doc"]["document_number"] == "2026-00002"
    assert next_page.url.endswith("page=2") and next_page.callback == spider.parse_listing

    # A later listing page repeating the document still requests nothing.
    assert list(spider.parse_listing(_listing([_doc("2026-00002")]))) == []


def test_parse_document_carries_what_ingest_needs(spider):
    doc = _doc("2026-00002", doc_type="Rule", effective_on="2026-11-30")
    response = HtmlResponse(
        url=doc["body_html_url"], body=b"<div id='summary'><p>Summary.</p></div>", encoding="utf-8"
    )
    (item,) = spider.parse_document(response, doc=doc)

    # The public page is the citation; the body endpoint is only where text came from.
    assert item["url"] == doc["html_url"]
    assert item["content_type"] == "text/html"
    assert "Summary." in item["content"]
    assert item["meta"] == {
        "document_number": "2026-00002",
        "title": doc["title"],
        "type": "Rule",
        "publication_date": "2026-09-29",
        "effective_on": "2026-11-30",
        "agencies": ["Homeland Security Department", "U.S. Citizenship and Immigration Services"],
        "cfr_references": [{"title": 8, "part": "244"}],
    }
