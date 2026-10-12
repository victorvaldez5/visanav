"""Removal tracking: telling ingest which pages have gone from a source.

Crawls are incremental, so a feed only ever adds or updates pages. A spider that
can tell a page has gone emits a tombstone for it (``removed``), and ingest drops
it from the merged snapshot. Two ways of telling, for two kinds of spider:

- ``CompleteEnumerationMixin``: the spider lists its whole source on every crawl
  (a bulk file, a complete index), so any URL its manifest knows but this crawl
  did not see is gone.
- ``MissCountingMixin``: the spider follows links, so one absence proves little
  (a missed link, a failed request). A page is gone only once several healthy
  crawls in a row have not seen it.

Both refuse to act on a crawl that cannot be trusted, and both refuse to remove
an implausibly large share of what they know in one crawl, so an outage, a block
or a half-published file at the source can never wipe a corpus.
"""
from scrapy import Request, signals
from scrapy.exceptions import DontCloseSpider

from .health import crawl_problems
from .items import ScrapedItem


class _RemovalsMixin:
    """The shared part: getting tombstones into the feed, and the cap."""

    # A source loses a page now and then, not a tenth of itself in one crawl.
    # Past this share of the manifest the source is assumed to be broken (a
    # well-formed but incomplete file, a redesign that hides the links) and
    # nothing is removed.
    max_removal_fraction = 0.1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls = set()
        self.removals_refused = False
        self._removals_emitted = False

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.emit_removals_when_idle, signal=signals.spider_idle)
        return spider

    def removed_items(self):
        raise NotImplementedError

    def _crawl_problems(self):
        """Why this crawl cannot say what has gone (empty if it can): the health
        check as it stands at idle, before the crawl closes."""
        return crawl_problems(self.crawler.stats.get_stats(), self, finished=False)

    def _tombstones(self, gone):
        """Tombstones for ``gone``, or none at all if that is too many to believe."""
        # ContentHashPipeline publishes the manifest's URLs when the spider opens.
        known = getattr(self, "manifest_urls", frozenset())
        if len(gone) > self.max_removal_fraction * len(known):
            self.removals_refused = True
            self.logger.error(
                "%d of %d known pages are missing, more than a crawl may remove; "
                "assuming the source is incomplete and removing nothing",
                len(gone), len(known),
            )
            return None
        return [ScrapedItem(url=url, removed=True) for url in sorted(gone)]

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
        for item in items:
            self.logger.info("removed at the source: %s", item["url"])
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


class CompleteEnumerationMixin(_RemovalsMixin):
    """Mix into a spider (before ``scrapy.Spider``) that sees every page each crawl.

    The spider calls ``mark_seen(url)`` for every item it yields (changed or
    not) and uses ``mark_failed`` as the errback of every request.

    Only a healthy crawl removes anything. A failed request, an error while
    parsing or far fewer pages than usual all leave pages unseen that are still
    at the source, so such a crawl emits no tombstones.
    """

    complete_enumeration = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.crawl_failed = False

    def mark_seen(self, url):
        self.seen_urls.add(url)

    def mark_failed(self, failure=None):
        self.crawl_failed = True
        self.logger.error("request failed, so this crawl will emit no removals: %s", failure)

    def removed_items(self):
        """Tombstones for manifest URLs this crawl did not see (none if unclean)."""
        if not self.seen_urls:
            return []
        problems = self._crawl_problems()
        if problems:
            self.logger.warning(
                "emitting no removals, the crawl is not healthy: %s", "; ".join(problems)
            )
            return []
        known = getattr(self, "manifest_urls", frozenset())
        return self._tombstones(known - self.seen_urls) or []


class MissCountingMixin(_RemovalsMixin):
    """Mix into a link-following spider (before ``scrapy.Spider``).

    Nothing to call: ContentHashPipeline notes every page the crawl yields in
    ``seen_urls`` and hands over the miss counts so far (``manifest_misses``).
    When the crawl goes idle, a page not seen has its count raised; one that
    reaches ``removal_after_misses`` is removed. The new counts go back to the
    pipeline as ``missed_counts`` and are saved with the manifest.

    Only a healthy crawl counts. If the crawl fails its health check (requests
    failing, parse errors, far fewer pages than usual) no count moves and
    nothing is removed, so a block or an outage never starts pages toward
    removal.
    """

    # Consecutive healthy crawls a page must be absent from before it is
    # removed. On a weekly schedule, 2 is about two weeks.
    removal_after_misses = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set only by a healthy crawl; None tells the pipeline to keep its counts.
        self.missed_counts = None

    def removed_items(self):
        problems = self._crawl_problems()
        if problems:
            self.logger.warning(
                "not counting missing pages, the crawl is not healthy: %s", "; ".join(problems)
            )
            return []

        known = getattr(self, "manifest_urls", frozenset())
        previous = getattr(self, "manifest_misses", {})
        counts = {url: previous.get(url, 0) + 1 for url in known - self.seen_urls}
        gone = {url for url, count in counts.items() if count >= self.removal_after_misses}
        tombstones = self._tombstones(gone)
        if tombstones is None:
            return []  # refused: leave every count where it was
        self.missed_counts = {url: n for url, n in counts.items() if url not in gone}
        return tombstones
