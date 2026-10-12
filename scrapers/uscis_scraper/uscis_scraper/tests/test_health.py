from types import SimpleNamespace

from ..health import crawl_problems

# The stats of a healthy weekly USCIS crawl, in miniature.
_HEALTHY = {
    "finish_reason": "finished",
    "downloader/request_count": 1001,
    "downloader/response_status_count/200": 1000,
    "downloader/response_status_count/404": 1,  # one dead link is normal
    "item_scraped_count": 30,
    "item_dropped_count": 950,  # unchanged pages were still seen
    "feedexport/success_count/S3FeedStorage": 1,
}
_USCIS = SimpleNamespace(min_items_seen=500)


def _stats(**changes):
    return {**_HEALTHY, **changes}


def test_healthy_crawl_has_no_problems():
    assert crawl_problems(_HEALTHY, _USCIS) == []
    # A crawl with nothing new is healthy for a spider with no floor.
    quiet = _stats(item_scraped_count=0, item_dropped_count=0)
    assert crawl_problems(quiet, SimpleNamespace()) == []


def test_blocked_crawl_is_a_problem():
    blocked = {
        "finish_reason": "finished",
        "downloader/request_count": 3,
        "downloader/response_status_count/403": 3,
    }
    problems = crawl_problems(blocked, _USCIS)
    assert "no request succeeded" in problems
    assert "only 0 item(s) seen, expected at least 500" in problems


def test_mostly_failing_requests_are_a_problem():
    flaky = _stats(**{"downloader/response_status_count/503": 400})
    assert "401 of 1401 requests failed" in crawl_problems(flaky, _USCIS)


def test_unstored_feed_is_a_problem():
    stats = _stats(**{"feedexport/failed_count/S3FeedStorage": 1})
    assert crawl_problems(stats, _USCIS) == ["the feed could not be stored"]
    # A feed that never opened is not counted as failed, only as not stored.
    never_opened = {k: v for k, v in _HEALTHY.items() if not k.startswith("feedexport/")}
    assert crawl_problems(never_opened, _USCIS) == ["the feed could not be stored"]


def test_interrupted_crawl_is_a_problem():
    assert crawl_problems(_stats(finish_reason="shutdown"), _USCIS) == [
        "the crawl ended as 'shutdown', not 'finished'"
    ]


def test_parse_errors_and_a_shrunken_site_are_problems():
    stats = _stats(**{"spider_exceptions/AttributeError": 2}, item_dropped_count=100)
    assert crawl_problems(stats, _USCIS) == [
        "2 page(s) raised an error while being parsed",
        "only 130 item(s) seen, expected at least 500",
    ]


def test_removal_tracking_failures_are_problems():
    failed = SimpleNamespace(crawl_failed=True, removals_refused=False)
    refused = SimpleNamespace(crawl_failed=False, removals_refused=True)
    assert crawl_problems(_HEALTHY, failed) == [
        "a request failed, so removed pages were not worked out"
    ]
    assert crawl_problems(_HEALTHY, refused) == [
        "too many known pages were missing, so none were removed"
    ]
