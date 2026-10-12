import pytest
from scrapy.exceptions import DontCloseSpider
from scrapy.http import XmlResponse

from ..spiders.ecfr_spider import EcfrSpider

# The shape of GPO's eCFR bulk XML: chapters hold parts, parts hold sections
# (DIV8) and appendices (DIV9), optionally inside subparts.
_TITLE_22 = """<?xml version="1.0" encoding="UTF-8" ?>
<DLPSTEXTCLASS><TEXT><BODY><ECFRBRWS>
<DIV1 N="1" TYPE="TITLE"><HEAD>Title 22—Foreign Relations</HEAD>
<DIV3 N="I" TYPE="CHAPTER"><HEAD>CHAPTER I—DEPARTMENT OF STATE</HEAD>
<DIV5 N="41" TYPE="PART"><HEAD>PART 41—VISAS</HEAD>
<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A—Passport and Visas Not Required</HEAD>
<DIV8 N="§ 41.0" TYPE="SECTION"><HEAD>§ 41.0   Definitions.</HEAD>
<P>For purposes of this part and part 42:</P><CITA>[81 FR 5907, Feb. 4, 2016]</CITA></DIV8>
<DIV8 N="§ 41.1" TYPE="SECTION"><HEAD>§ 41.1   [Reserved]</HEAD></DIV8>
<DIV8 N="§§ 41.4-41.9" TYPE="SECTION"><HEAD>§§ 41.4-41.9   [Reserved]</HEAD></DIV8>
</DIV6>
</DIV5>
<DIV5 N="62" TYPE="PART"><HEAD>PART 62—EXCHANGE VISITOR PROGRAM</HEAD>
<DIV9 N="Appendix E" TYPE="APPENDIX"><HEAD>Appendix E to Part 62—Unskilled Occupations</HEAD>
<P>For purposes of 22 CFR 62.22, the following are unskilled occupations.</P></DIV9>
</DIV5>
<DIV5 N="120" TYPE="PART"><HEAD>PART 120—ARMS REGULATIONS</HEAD>
<DIV8 N="§ 120.1" TYPE="SECTION"><HEAD>§ 120.1   General.</HEAD><P>Out of scope.</P></DIV8>
</DIV5>
</DIV3></DIV1></ECFRBRWS></BODY></TEXT></DLPSTEXTCLASS>"""


@pytest.fixture
def spider():
    return EcfrSpider()


def _title_response(title, body):
    url = EcfrSpider.BULK_URL.format(title=title)
    return XmlResponse(url=url, body=body.encode("utf-8"), encoding="utf-8")


def test_parse_title_yields_one_item_per_in_scope_section(spider):
    items = list(spider.parse_title(_title_response(22, _TITLE_22), title=22))

    # Part 120 is outside the coverage for title 22, and reserved sections
    # (single or ranges) carry no text.
    assert [item["meta"]["citation"] for item in items] == [
        "22 CFR 41.0",
        "22 CFR Appendix E to Part 62",
    ]

    section, appendix = items
    assert section["url"] == "https://www.ecfr.gov/current/title-22/section-41.0"
    assert section["content_type"] == "application/xml"
    assert "For purposes of this part" in section["content"]
    assert section["meta"] == {
        "citation": "22 CFR 41.0",
        "heading": "Definitions.",
        "kind": "section",
        "title": 22,
        "chapter": "I",
        "part": "41",
    }

    assert appendix["url"] == (
        "https://www.ecfr.gov/current/title-22/part-62/appendix-Appendix%20E%20to%20Part%2062"
    )
    assert appendix["meta"]["heading"] == "Unskilled Occupations"
    assert appendix["meta"]["kind"] == "appendix"


def _remember(spider, *gone):
    """Give the spider a manifest from an earlier crawl: the pages named in
    `gone`, plus enough pages this crawl also sees that losing those few is
    plausible (see max_removal_fraction)."""
    still_there = {f"https://www.ecfr.gov/current/title-8/section-1.{n}" for n in range(1, 31)}
    for url in still_there:
        spider.mark_seen(url)
    spider.manifest_urls = frozenset(still_there | set(gone))


def test_whole_title_coverage_keeps_every_part(spider):
    # Title 8 is covered in full, so the part that title 22 leaves out is kept.
    items = list(spider.parse_title(_title_response(8, _TITLE_22), title=8))
    assert "8 CFR 120.1" in [item["meta"]["citation"] for item in items]


def test_clean_crawl_reports_sections_that_disappeared(spider):
    gone = "https://www.ecfr.gov/current/title-22/section-41.99"
    kept = "https://www.ecfr.gov/current/title-22/section-41.0"
    _remember(spider, gone, kept)
    list(spider.parse_title(_title_response(22, _TITLE_22), title=22))

    removed = spider.removed_items()
    assert [dict(item) for item in removed] == [{"url": gone, "removed": True}]


def test_unclean_crawl_reports_no_removals(spider):
    spider.manifest_urls = frozenset({"https://www.ecfr.gov/current/title-22/section-41.99"})

    # Nothing was seen at all (e.g. the source served an empty file).
    assert spider.removed_items() == []

    # One title failed to download: the sections it would have listed look
    # missing, but they must not be reported as removed.
    list(spider.parse_title(_title_response(22, _TITLE_22), title=22))
    spider.mark_failed("timeout")
    assert spider.removed_items() == []


def test_implausibly_many_missing_sections_are_not_removed(spider):
    # The file parsed cleanly but lists one section where the manifest knows
    # twenty: far likelier a half-published file than nineteen repeals.
    kept = "https://www.ecfr.gov/current/title-22/section-41.0"
    spider.manifest_urls = frozenset(
        {kept} | {f"https://www.ecfr.gov/current/title-22/section-41.{n}" for n in range(100, 119)}
    )
    list(spider.parse_title(_title_response(22, _TITLE_22), title=22))

    assert spider.removed_items() == []
    assert spider.removals_refused  # and the crawl is reported as failed (health.py)


class _Engine:
    def __init__(self):
        self.requests = []

    def crawl(self, request):
        self.requests.append(request)


class _Crawler:
    def __init__(self):
        self.engine = _Engine()


def test_idle_spider_routes_removals_into_the_feed_once(spider):
    spider.crawler = _Crawler()
    _remember(spider, "https://www.ecfr.gov/current/title-22/section-41.99")
    list(spider.parse_title(_title_response(22, _TITLE_22), title=22))

    # First idle: keep the spider open for one request whose callback yields
    # the tombstones (items can only reach the feed from a callback).
    with pytest.raises(DontCloseSpider):
        spider.emit_removals_when_idle()
    (request,) = spider.crawler.engine.requests
    items = list(request.callback(None, **request.cb_kwargs))
    assert [item["url"] for item in items] == [
        "https://www.ecfr.gov/current/title-22/section-41.99"
    ]

    # Second idle (after that request): nothing more, so the spider closes.
    spider.emit_removals_when_idle()
    assert len(spider.crawler.engine.requests) == 1
