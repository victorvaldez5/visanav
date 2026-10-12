import scrapy
from urllib.parse import quote

from ..enumeration import CompleteEnumerationMixin
from ..items import ScrapedItem


class EcfrSpider(CompleteEnumerationMixin, scrapy.Spider):
    """Current text of the immigration-related parts of the CFR, one item per section.

    Reads the daily eCFR bulk XML that GPO publishes on govinfo (one file per
    CFR title) rather than ecfr.gov, whose robots.txt disallows its full-text
    API. Each item's ``url`` is still the section's public ecfr.gov page, so
    citations are clickable.

    Every crawl sees every in-scope section, so sections that disappear are
    emitted as removals (see CompleteEnumerationMixin).
    """

    name = "ecfr"
    allowed_domains = ["govinfo.gov"]
    custom_settings = {"USER_AGENT": "visanav-scraper (+https://github.com/victorvaldez5)"}

    # CFR coverage: title -> parts to keep (None keeps the whole title).
    # Widen coverage here.
    COVERAGE = {
        8: None,  # Aliens and Nationality (DHS and EOIR)
        20: {"655", "656"},  # temporary and permanent labor certification
        22: {"40", "41", "42", "62"},  # visas and exchange visitors
    }
    BULK_URL = "https://www.govinfo.gov/bulkdata/ECFR/title-{title}/ECFR-title{title}.xml"
    # The coverage above is about 1,400 sections; far fewer means a title came
    # back incomplete (see health.py).
    min_items_seen = 1000
    PUBLIC_URL = "https://www.ecfr.gov/current/title-{title}"

    async def start(self):
        for title in self.COVERAGE:
            yield scrapy.Request(
                self.BULK_URL.format(title=title),
                callback=self.parse_title,
                errback=self.mark_failed,
                cb_kwargs={"title": title},
            )

    def parse_title(self, response, title):
        parts = self.COVERAGE[title]
        document = scrapy.Selector(text=response.text, type="xml")
        for part in document.xpath('//DIV5[@TYPE="PART"]'):
            number = part.attrib.get("N", "")
            if parts is not None and number not in parts:
                continue
            chapter = part.xpath('ancestor::DIV3[@TYPE="CHAPTER"]/@N').get()
            for node in part.xpath('.//DIV8[@TYPE="SECTION"] | .//DIV9[@TYPE="APPENDIX"]'):
                item = self._item(node, title, chapter, number)
                if item is not None:
                    self.mark_seen(item["url"])
                    yield item

    def _item(self, node, title, chapter, part):
        head = " ".join(" ".join(node.xpath("./HEAD//text()").getall()).split())
        # Reserved sections are placeholders with a heading and no text.
        if "[Reserved]" in head or not node.xpath("./*[not(self::HEAD)]"):
            return None

        base = self.PUBLIC_URL.format(title=title)
        if node.attrib.get("TYPE") == "APPENDIX":
            # "Appendix A to Subpart F of Part 655—U.S. Seaports"
            label, _, heading = head.partition("\u2014")
            label = label.strip()
            kind = "appendix"
            citation = f"{title} CFR {label}"
            url = f"{base}/part-{part}/appendix-{quote(label)}"
        else:
            # N is "§ 274a.12"; a "§§ 1.1-1.9" range is a block of reserved numbers.
            number = node.attrib.get("N", "")
            if number.startswith("\u00a7\u00a7"):
                return None
            identifier = number.lstrip("\u00a7").strip()
            kind = "section"
            citation = f"{title} CFR {identifier}"
            heading = head.removeprefix(number).strip()
            url = f"{base}/section-{quote(identifier)}"

        return ScrapedItem(
            url=url,
            content_type="application/xml",
            content=node.get(),
            meta={
                "citation": citation,
                "heading": heading.strip(),
                "kind": kind,
                "title": title,
                "chapter": chapter,
                "part": part,
            },
        )
