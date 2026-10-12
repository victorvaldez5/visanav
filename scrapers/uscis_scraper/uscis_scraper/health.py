"""Decide whether a finished crawl can be trusted.

Scrapy exits 0 whenever the crawl ran to the end, even if every request was
blocked or the feed could not be stored, so a scheduled crawl would report
success while producing nothing. ``crawl_problems`` reads the crawl's stats and
the project's ``crawl`` command (commands/crawl.py) exits non-zero if it finds
any, which is what makes a bad run show as failed on Railway.
"""

# Above this share of failed requests the source was blocking or down, not flaky.
MAX_FAILED_REQUEST_SHARE = 0.2


def _sum(stats, prefix):
    return sum(count for key, count in stats.items() if key.startswith(prefix) and count)


def feed_was_stored(stats):
    """True only on positive evidence: a feed that failed to open is never
    counted as failed by Scrapy, it is just never counted as stored."""
    return bool(_sum(stats, "feedexport/success_count")) and not _sum(
        stats, "feedexport/failed_count"
    )


def crawl_problems(stats, spider=None, finished=True):
    """Return the reasons this crawl should count as failed (empty if healthy).

    With ``finished=False`` the crawl is judged as it stands once every request
    has been handled but before it closes, when how it finished and whether its
    feed was stored are not yet known.
    """
    problems = []

    if finished:
        reason = stats.get("finish_reason")
        if reason != "finished":
            problems.append(f"the crawl ended as {reason!r}, not 'finished'")

        if not feed_was_stored(stats):
            problems.append("the feed could not be stored")

    succeeded = _sum(stats, "downloader/response_status_count/2") + _sum(
        stats, "downloader/response_status_count/3"
    )
    failed = (
        _sum(stats, "downloader/response_status_count/4")
        + _sum(stats, "downloader/response_status_count/5")
        + stats.get("downloader/exception_count", 0)
    )
    if not succeeded:
        problems.append("no request succeeded")
    elif failed / (succeeded + failed) > MAX_FAILED_REQUEST_SHARE:
        problems.append(f"{failed} of {succeeded + failed} requests failed")

    errors = _sum(stats, "spider_exceptions/")
    if errors:
        problems.append(f"{errors} page(s) raised an error while being parsed")

    # Unchanged pages are dropped by the pipeline but were still seen.
    seen = stats.get("item_scraped_count", 0) + stats.get("item_dropped_count", 0)
    expected = getattr(spider, "min_items_seen", 0)
    if seen < expected:
        problems.append(f"only {seen} item(s) seen, expected at least {expected}")

    if getattr(spider, "crawl_failed", False):
        problems.append("a request failed, so removed pages were not worked out")
    if getattr(spider, "removals_refused", False):
        problems.append("too many known pages were missing, so none were removed")

    return problems
