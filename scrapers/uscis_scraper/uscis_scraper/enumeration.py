"""Removal tracking for spiders that list their whole source on every crawl.

Crawls are incremental, so a feed only ever adds or updates pages. A spider that
enumerates its source completely can also say what has gone: any URL its
manifest knows but this crawl did not see is emitted to the feed as a tombstone
(``removed``), and ingest drops it from the merged snapshot.

Only a crawl that finished cleanly may do that. A crawl that failed partway, saw
nothing at all, or would remove an implausibly large share of what it knows
emits no tombstones, so an outage or a half-published file at the source can
never wipe a corpus.
"""
from scrapy import Request, signals
from scrapy.exceptions import DontCloseSpider

from .items import ScrapedItem


class CompleteEnumerationMixin:
    """Mix into a spider (before ``scrapy.Spider``) that sees every page each crawl.

    The spider calls ``mark_seen(url)`` for every item it yields (changed or
    not) and uses ``mark_failed`` as the errback of every request.
    """

    complete_enumeration = True
    # A source loses a page now and then, not a tenth of itself in one crawl.
    # Past this share of the manifest the source is assumed to be broken (a
    # well-formed but incomplete file) and nothing is removed.
    max_removal_fraction = 0.1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls = set()
        self.crawl_failed = False
        self.removals_refused = False
        self._removals_emitted = False

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.emit_removals_when_idle, signal=signals.spider_idle)
        return spider

    def mark_seen(self, url):
        self.seen_urls.add(url)

    def mark_failed(self, failure=None):
        self.crawl_failed = True
        self.logger.error("request failed, so this crawl will emit no removals: %s", failure)

    def removed_items(self):
        """Tombstones for manifest URLs this crawl did not see (none if unclean)."""
        if self.crawl_failed or not self.seen_urls:
            return []
        # ContentHashPipeline publishes the manifest's URLs when the spider opens.
        known = getattr(self, "manifest_urls", frozenset())
        gone = sorted(known - self.seen_urls)
        if len(gone) > self.max_removal_fraction * len(known):
            self.removals_refused = True
            self.logger.error(
                "%d of %d known pages are missing, more than a crawl may remove; "
                "assuming the source is incomplete and removing nothing",
                len(gone), len(known),
            )
            return []
        return [ScrapedItem(url=url, removed=True) for url in gone]

    def emit_removals_when_idle(self):
        # The spider goes idle once, after every request has been handled. Items
        # can only enter the pipelines from a callback, so route the tombstones
        # through one last no-op request and keep the spider open for it.
        if self._removals_emitted:
            return
        self._removals_emitted = True
        items = self.removed_items()
        if not items:
            return
        self.logger.info("emitting %d removal(s)", len(items))
        self.crawler.engine.crawl(
            Request(
                "data:,",
                callback=self.yield_removals,
                cb_kwargs={"items": items},
                dont_filter=True,
                meta={"allow_offsite": True, "dont_obey_robotstxt": True},
            )
        )
        raise DontCloseSpider

    def yield_removals(self, response, items):
        yield from items
