import hashlib
import json
import os
from types import SimpleNamespace

import pytest
from scrapy import Request
from scrapy.exceptions import NotConfigured, DropItem
from scrapy.utils.test import get_crawler
from ..pipelines import HTMLPagesPipeline, NamedFilesPipeline, ContentHashPipeline


class DummySignals:
    def __init__(self):
        self.connected = {}

    def connect(self, receiver, signal):
        self.connected[signal] = receiver


class DummyStats:
    def __init__(self):
        self.values = {}

    def get_stats(self):
        return self.values


class DummyCrawler:
    def __init__(self, settings):
        self.settings = settings
        self.signals = DummySignals()
        self.stats = DummyStats()


def _through(pipeline, item, spider=None):
    """Run an item through the hash pipeline as a crawl does when every later
    pipeline succeeds: Scrapy then fires item_scraped, which records the page."""
    out = pipeline.process_item(item, spider)
    pipeline.item_scraped(out)
    return out


def test_html_pages_pipeline_not_configured():
    crawler = DummyCrawler({})
    with pytest.raises(NotConfigured):
        HTMLPagesPipeline.from_crawler(crawler)


def test_html_pages_pipeline_local(tmp_path):
    settings = {
        "LOCAL_TEST": True,
        "LOCAL_FILES": str(tmp_path),
    }
    pipeline = HTMLPagesPipeline.from_crawler(DummyCrawler(settings))

    item = {
        "url": "https://example.com/path/page",
        "content_type": "text/html",
        "content": "<h1>Hello</h1>",
    }
    out = pipeline.process_item(item, spider=None)
    assert out is item

    # expect file at <tmp>/html/path/page.html
    target = tmp_path / "html" / "path" / "page.html"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "<h1>Hello</h1>"


def test_named_files_pipeline_requests_and_path():
    pipe = NamedFilesPipeline(crawler=get_crawler(), store_uri="unused")
    item = {
        "file_urls": ["http://foo/bar/baz.pdf"],
        "parent_page": "https://site/ar-11",
    }
    reqs = list(pipe.get_media_requests(item, None))
    assert len(reqs) == 1
    r = reqs[0]
    assert isinstance(r, Request)
    assert r.url == "http://foo/bar/baz.pdf"
    assert r.meta["parent_page"] == item["parent_page"]

    # test file_path naming: non-instruction PDFs bucket under pdf/forms/
    fake = Request("http://foo/x/y.pdf", meta={"parent_page": item["parent_page"]})
    out_path = pipe.file_path(fake)
    assert out_path == os.path.join("pdf", "forms", "y.pdf")


@pytest.fixture
def html_item():
    return {
        "url": "https://example.com/some/path",
        "content_type": "text/html",
        "content": "<h1>OK</h1>",
    }


def test_html_pipeline_skips_non_html(tmp_path, html_item):
    settings = {"LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
    pipeline = HTMLPagesPipeline.from_crawler(DummyCrawler(settings))

    pdf_item = dict(html_item, content_type="application/pdf")
    out = pipeline.process_item(pdf_item, spider=None)
    # Should simply return the item without writing any file
    assert out is pdf_item
    assert not (tmp_path / "html").exists()


def test_html_pipeline_root_fallback(tmp_path):
    settings = {"LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
    pipeline = HTMLPagesPipeline.from_crawler(DummyCrawler(settings))

    item = {
        "url": "https://example.com/",
        "content_type": "text/html",
        "content": "ROOT",
    }
    pipeline.process_item(item, spider=None)
    # path='' -> fallback to 'root'
    target = tmp_path / "html" / "root.html"
    assert target.exists()
    assert target.read_text() == "ROOT"


def test_html_pipeline_xhtml_local(tmp_path):
    settings = {"LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
    pipeline = HTMLPagesPipeline.from_crawler(DummyCrawler(settings))

    # simulate an .xhtml URL with query params & fragments
    url = "https://host/doc.xhtml?req=granuleid:USC-prelim-title8-section1101&num=0&edition=prelim"
    item = {"url": url, "content_type": "text/html", "content": "<p>XHTML</p>"}
    pipeline.process_item(item, spider=None)
    # should write under <netloc>/<last‐param>.html, e.g. host/section=5.html
    # splitting logic takes 'section=5' as key
    expected = tmp_path / "html" / "host/USC-prelim-title8-section1101.html"
    assert expected.exists()
    assert "XHTML" in expected.read_text()


def test_named_files_pipeline_no_urls():
    pipe = NamedFilesPipeline(crawler=get_crawler(), store_uri="unused")
    # item without file_urls or empty list
    for itm in ({}, {"file_urls": []}):
        reqs = list(pipe.get_media_requests(itm, info=None))
        assert reqs == []


def test_named_files_pipeline_uncategorized_path():
    pipe = NamedFilesPipeline(crawler=get_crawler(), store_uri="u")
    # a plain form PDF (no instruction pattern) buckets under pdf/forms/
    req = Request("http://x.com/a.pdf", meta={})
    path = pipe.file_path(req)
    assert path == os.path.join("pdf", "forms", "a.pdf")


def test_named_files_pipeline_multiple_requests():
    pipe = NamedFilesPipeline(crawler=get_crawler(), store_uri="dummy://")
    item = {
        "file_urls": ["http://foo.com/files/a.pdf", "https://bar.org/b.txt"],
        "parent_page": "https://example.com/section",
    }
    reqs = list(pipe.get_media_requests(item, info=None))
    # should have one Request per URL, preserving order and meta
    assert len(reqs) == 2
    assert [r.url for r in reqs] == item["file_urls"]
    assert all(r.meta.get("parent_page") == item["parent_page"] for r in reqs)


def test_named_files_pipeline_nested_parent_path():
    pipe = NamedFilesPipeline(crawler=get_crawler(), store_uri="dummy://")
    # a deeply nested parent_page path
    parent = "https://site.com/a/b/c/d"
    req = Request("http://cdn.com/doc.pdf", meta={"parent_page": parent})
    out = pipe.file_path(req)
    # non-instruction PDFs land under pdf/forms/ regardless of parent path
    expected = os.path.join("pdf", "forms", "doc.pdf")
    assert out == expected


def _content_hash_pipeline(tmp_path):
    settings = {"LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
    return ContentHashPipeline.from_crawler(DummyCrawler(settings))


def test_content_hash_stamps_new_item(tmp_path):
    pipe = _content_hash_pipeline(tmp_path)
    pipe.open_spider(spider=None)
    item = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"}
    out = pipe.process_item(item, spider=None)
    assert out is item
    assert item["content_hash"] == hashlib.sha256(b"<h1>A</h1>").hexdigest()


def test_content_hash_drops_unchanged_across_runs(tmp_path):
    item = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"}

    # First run: new item passes, manifest persisted on close.
    run1 = _content_hash_pipeline(tmp_path)
    run1.open_spider(spider=None)
    _through(run1, dict(item))
    run1.close_spider(spider=None)
    assert (tmp_path / "manifests" / "uscis.json").exists()

    # Second run: identical content is dropped before the storage sink.
    run2 = _content_hash_pipeline(tmp_path)
    run2.open_spider(spider=None)
    with pytest.raises(DropItem):
        run2.process_item(dict(item), spider=None)


def test_content_hash_passes_changed_item(tmp_path):
    run1 = _content_hash_pipeline(tmp_path)
    run1.open_spider(spider=None)
    _through(run1, {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"})
    run1.close_spider(spider=None)

    run2 = _content_hash_pipeline(tmp_path)
    run2.open_spider(spider=None)
    changed = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>B</h1>"}
    out = run2.process_item(changed, spider=None)
    assert out is changed  # different content -> not dropped


def test_content_hash_skips_pdf(tmp_path):
    pipe = _content_hash_pipeline(tmp_path)
    pipe.open_spider(spider=None)
    pdf = {"url": "https://x/a.pdf", "content_type": "application/pdf"}
    out = pipe.process_item(pdf, spider=None)
    assert out is pdf
    assert "content_hash" not in pdf


@pytest.mark.parametrize(
    "url, expected_name",
    [
        # URL ending in slash yields empty basename -> treat as just folder
        ("http://x.com/folder/", ""),
        # URL with query params
        ("http://x.com/path/file.mp3?download=true", "file.mp3"),
        # URL without extension
        ("http://x.com/onlyname", "onlyname"),
    ],
)
def test_named_files_pipeline_various_basenames(url, expected_name):
    pipe = NamedFilesPipeline(crawler=get_crawler(), store_uri="dummy://")
    req = Request(url, meta={"parent_page": "https://host/"})
    path = pipe.file_path(req)
    # split the returned path
    segments = path.split(os.sep)
    # first segment is 'pdf', second is 'uncategorized'
    assert segments[0] == "pdf"
    # last segment matches expected basename (might be empty string)
    assert segments[-1] == expected_name


# -- multiple sources -----------------------------------------------------------


def _spider(name):
    return SimpleNamespace(name=name)


def test_pages_pipeline_namespaces_other_sources(tmp_path):
    settings = {"LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
    pipeline = HTMLPagesPipeline.from_crawler(DummyCrawler(settings))

    section = {
        "url": "https://www.ecfr.gov/current/title-8/section-274a.12",
        "content_type": "application/xml",
        "content": "<DIV8/>",
    }
    pipeline.process_item(section, spider=_spider("ecfr"))
    stored = tmp_path / "pages" / "ecfr" / "current" / "title-8" / "section-274a.12.xml"
    assert stored.read_text() == "<DIV8/>"

    # USCIS pages keep the keys they have always had.
    page = {"url": "https://www.uscis.gov/i-485", "content_type": "text/html", "content": "<p/>"}
    pipeline.process_item(page, spider=_spider("uscis"))
    assert (tmp_path / "html" / "i-485.html").exists()


def test_content_hash_keeps_one_manifest_per_source(tmp_path):
    item = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"}

    first = _content_hash_pipeline(tmp_path)
    first.open_spider(_spider("ecfr"))
    _through(first, dict(item), _spider("ecfr"))
    first.close_spider(_spider("ecfr"))

    # Another source has never seen this URL, so its crawl is not short-circuited
    # by the first source's manifest.
    other = _content_hash_pipeline(tmp_path)
    spider = _spider("federal-register")
    other.open_spider(spider)
    assert spider.manifest_urls == frozenset()
    assert _through(other, dict(item), spider)
    other.close_spider(spider)

    assert json.loads((tmp_path / "manifests" / "ecfr.json").read_text()).keys() == {"https://x/a"}
    assert (tmp_path / "manifests" / "federal-register.json").exists()

    # The source's own next crawl sees what it already has.
    again = _content_hash_pipeline(tmp_path)
    spider = _spider("ecfr")
    again.open_spider(spider)
    assert spider.manifest_urls == {"https://x/a"}
    with pytest.raises(DropItem):
        again.process_item(dict(item), spider)


def test_content_hash_reads_legacy_uscis_manifest_once(tmp_path):
    item = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"}
    digest = hashlib.sha256(b"<h1>A</h1>").hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps({"https://x/a": digest}))

    # No other source falls back to the shared pre-namespacing manifest.
    other = _content_hash_pipeline(tmp_path)
    other.open_spider(_spider("ecfr"))
    assert other.manifest == {}

    # USCIS does, so its first crawl after the change re-emits nothing, and it
    # rewrites the manifest under its own name even though nothing changed.
    run = _content_hash_pipeline(tmp_path)
    run.open_spider(_spider("uscis"))
    with pytest.raises(DropItem):
        run.process_item(dict(item), _spider("uscis"))
    run.close_spider(_spider("uscis"))
    namespaced = tmp_path / "manifests" / "uscis.json"
    assert json.loads(namespaced.read_text()) == {"https://x/a": {"hash": digest, "missed": 0}}

    # From then on the namespaced manifest is the one that counts.
    (tmp_path / "manifest.json").write_text("{}")
    later = _content_hash_pipeline(tmp_path)
    later.open_spider(_spider("uscis"))
    assert later.manifest == {"https://x/a": digest}


def test_content_hash_tombstone_forgets_the_url(tmp_path):
    spider = _spider("ecfr")
    run1 = _content_hash_pipeline(tmp_path)
    run1.open_spider(spider)
    for name in ("a", "b"):
        _through(
            run1, {"url": f"https://x/{name}", "content_type": "application/xml", "content": name}, spider
        )
    run1.close_spider(spider)

    run2 = _content_hash_pipeline(tmp_path)
    run2.open_spider(spider)
    tombstone = {"url": "https://x/a", "removed": True}
    assert _through(run2, tombstone, spider) is tombstone  # reaches the feed
    run2.close_spider(spider)

    manifest = json.loads((tmp_path / "manifests" / "ecfr.json").read_text())
    assert manifest.keys() == {"https://x/b"}


class _FakeS3:
    """Just enough of an S3 client for the manifest and page sinks."""

    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)  # stands in for botocore's NoSuchKey

        class _Body:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data

        return {"Body": _Body(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body


def test_r2_keys_are_namespaced_per_source_with_uscis_fallback(tmp_path):
    digest = hashlib.sha256(b"<h1>A</h1>").hexdigest()
    s3 = _FakeS3({"raw/manifest.json": json.dumps({"https://x/a": digest}).encode()})

    # USCIS: the shared pre-namespacing manifest is honoured, then moved.
    uscis = ContentHashPipeline(str(tmp_path), local_test=False, bucket="b", s3_client=s3)
    uscis.open_spider(_spider("uscis"))
    assert uscis.manifest == {"https://x/a": digest}
    uscis.close_spider(_spider("uscis"))
    moved = {"https://x/a": {"hash": digest, "missed": 0}}
    assert json.loads(s3.objects["raw/manifests/uscis.json"]) == moved

    # Another source starts empty and writes only its own manifest and pages.
    ecfr = ContentHashPipeline(str(tmp_path), local_test=False, bucket="b", s3_client=s3)
    ecfr.open_spider(_spider("ecfr"))
    assert ecfr.manifest == {}
    item = {"url": "https://www.ecfr.gov/current/title-8/section-1.1",
            "content_type": "application/xml", "content": "<DIV8/>"}
    _through(ecfr, item, _spider("ecfr"))
    ecfr.close_spider(_spider("ecfr"))
    assert "raw/manifests/ecfr.json" in s3.objects
    assert json.loads(s3.objects["raw/manifests/uscis.json"]) == moved

    pages = HTMLPagesPipeline(str(tmp_path), local_test=False, bucket="b", s3_client=s3)
    pages.process_item(item, _spider("ecfr"))
    pages.process_item(
        {"url": "https://www.uscis.gov/i-485", "content_type": "text/html", "content": "<p/>"},
        _spider("uscis"),
    )
    assert "raw/pages/ecfr/current/title-8/section-1.1.xml" in s3.objects
    assert "raw/html/i-485.html" in s3.objects


# -- a page is only recorded once it is safely downstream -------------------------


def test_content_hash_forgets_a_page_that_never_reached_the_feed(tmp_path):
    item = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"}

    # The page passed the hash check, but a later pipeline (the raw-page upload,
    # say) raised, so Scrapy never fired item_scraped for it.
    run1 = _content_hash_pipeline(tmp_path)
    run1.open_spider(spider=None)
    run1.process_item(dict(item), spider=None)
    run1.close_spider(spider=None)

    # The next crawl must emit it again rather than skip it as already seen.
    run2 = _content_hash_pipeline(tmp_path)
    run2.open_spider(spider=None)
    assert run2.process_item(dict(item), spider=None)["content_hash"]


def _feeding_pipeline(tmp_path):
    """The hash pipeline as wired in a real crawl, where a feed is exported."""
    settings = {
        "LOCAL_TEST": True,
        "LOCAL_FILES": str(tmp_path),
        "FEED_URI": str(tmp_path / "items" / "feed.jsonl"),
    }
    crawler = DummyCrawler(settings)
    return ContentHashPipeline.from_crawler(crawler), crawler


def test_manifest_is_saved_only_after_the_feed_is_stored(tmp_path):
    item = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"}
    saved = tmp_path / "manifests" / "uscis.json"

    pipeline, crawler = _feeding_pipeline(tmp_path)
    pipeline.open_spider(spider=None)
    _through(pipeline, dict(item))
    # Pipelines close before the feed is uploaded: nothing is on disk yet.
    pipeline.close_spider(spider=None)
    assert not saved.exists()
    crawler.stats.values["feedexport/success_count/S3FeedStorage"] = 1
    pipeline.feed_exporter_closed()
    assert json.loads(saved.read_text()).keys() == {"https://x/a"}


def test_manifest_is_left_alone_when_the_feed_fails_to_store(tmp_path):
    item = {"url": "https://x/a", "content_type": "text/html", "content": "<h1>A</h1>"}

    pipeline, crawler = _feeding_pipeline(tmp_path)
    pipeline.open_spider(spider=None)
    _through(pipeline, dict(item))
    pipeline.close_spider(spider=None)
    crawler.stats.values["feedexport/failed_count/S3FeedStorage"] = 1
    pipeline.feed_exporter_closed()

    # The page is in no stored feed, so it must not be remembered as seen:
    # the next crawl emits it again.
    assert not (tmp_path / "manifests" / "uscis.json").exists()

    # Likewise when the feed could not even be opened: Scrapy then reports no
    # failure, only the absence of a stored feed.
    unopened, _ = _feeding_pipeline(tmp_path)
    unopened.open_spider(spider=None)
    _through(unopened, dict(item))
    unopened.feed_exporter_closed()
    assert not (tmp_path / "manifests" / "uscis.json").exists()

    retry, _ = _feeding_pipeline(tmp_path)
    retry.open_spider(spider=None)
    assert retry.process_item(dict(item), spider=None)["content_hash"]


def test_content_hash_ignores_markup_the_spider_calls_volatile(tmp_path):
    from ..spiders.uscis_spider import UscisSpider

    spider = UscisSpider()
    page = (
        '<div class="views js-view-dom-id-{view}">'
        '<span class="current-date__value"> {manual}</span>'
        '<span class="lawsInEffect">Text contains those laws in effect on {laws}</span>'
        "<p>{body}</p></div>"
    )
    first = page.format(view="1284625097f7", manual="September 11, 2026",
                        laws="September 13, 2026", body="The rule.")
    refetched = page.format(view="14681d6ad55a", manual="September 18, 2026",
                            laws="September 20, 2026", body="The rule.")
    amended = refetched.replace("The rule.", "The amended rule.")

    run1 = _content_hash_pipeline(tmp_path)
    run1.open_spider(spider)
    _through(run1, {"url": "https://x/a", "content_type": "text/html", "content": first}, spider)
    run1.close_spider(spider)

    run2 = _content_hash_pipeline(tmp_path)
    run2.open_spider(spider)
    # Same page, fetched a week later: only the per-fetch markup differs.
    with pytest.raises(DropItem):
        run2.process_item(
            {"url": "https://x/a", "content_type": "text/html", "content": refetched}, spider
        )
    # A real edit is still noticed, and the feed gets the page as fetched.
    out = run2.process_item(
        {"url": "https://x/a", "content_type": "text/html", "content": amended}, spider
    )
    assert out["content"] == amended


# -- pages that vanish from a link-following crawl (miss counting) ----------------

_SITE = [f"https://www.uscis.gov/page-{n}" for n in range(30)]
_GONE = _SITE[0]


def _uscis_crawl(tmp_path, urls, blocked=False, **spider_args):
    """One crawl of the given pages by the USCIS spider, through the hash
    pipeline, as far as the manifest it leaves behind.

    Returns the URLs it emitted removals for.
    """
    from ..spiders.uscis_spider import UscisSpider

    spider = UscisSpider(**spider_args)
    spider.min_items_seen = 20
    spider.crawler = DummyCrawler({})
    pipeline = _content_hash_pipeline(tmp_path)
    pipeline.open_spider(spider)

    stats = spider.crawler.stats.values
    for url in urls:
        item = {"url": url, "content_type": "text/html", "content": "<p>same every week</p>"}
        try:
            _through(pipeline, item, spider)
            stats["item_scraped_count"] = stats.get("item_scraped_count", 0) + 1
        except DropItem:
            stats["item_dropped_count"] = stats.get("item_dropped_count", 0) + 1
    if blocked:
        stats["downloader/response_status_count/403"] = 100
    stats["downloader/response_status_count/200"] = len(urls)

    # What the spider does when it goes idle, then what the pipelines do with it.
    removals = spider.removed_items()
    for tombstone in removals:
        _through(pipeline, tombstone, spider)
    pipeline.close_spider(spider)
    return [item["url"] for item in removals]


def _manifest(tmp_path):
    return json.loads((tmp_path / "manifests" / "uscis.json").read_text())


def test_page_missing_from_one_crawl_is_kept(tmp_path):
    _uscis_crawl(tmp_path, _SITE)
    assert _uscis_crawl(tmp_path, _SITE[1:]) == []

    manifest = _manifest(tmp_path)
    assert manifest[_GONE]["missed"] == 1
    assert all(manifest[url]["missed"] == 0 for url in _SITE[1:])


def test_page_missing_from_two_crawls_in_a_row_is_removed(tmp_path):
    _uscis_crawl(tmp_path, _SITE)
    _uscis_crawl(tmp_path, _SITE[1:])
    assert _uscis_crawl(tmp_path, _SITE[1:]) == [_GONE]

    # It is forgotten, so if the site brings it back it is emitted as new.
    assert _GONE not in _manifest(tmp_path)
    assert _uscis_crawl(tmp_path, _SITE) == []
    assert _manifest(tmp_path)[_GONE]["missed"] == 0


def test_page_that_comes_back_starts_over(tmp_path):
    _uscis_crawl(tmp_path, _SITE)
    _uscis_crawl(tmp_path, _SITE[1:])  # missed once
    _uscis_crawl(tmp_path, _SITE)  # back again
    assert _manifest(tmp_path)[_GONE]["missed"] == 0

    # One more absence is a first miss again, not the second.
    assert _uscis_crawl(tmp_path, _SITE[1:]) == []
    assert _manifest(tmp_path)[_GONE]["missed"] == 1


def test_unhealthy_crawl_counts_no_misses(tmp_path):
    _uscis_crawl(tmp_path, _SITE)
    _uscis_crawl(tmp_path, _SITE[1:])  # missed once, fairly

    # The site blocks most requests: half the pages look missing, and the page
    # already missed once looks missing a second time. None of that counts.
    assert _uscis_crawl(tmp_path, _SITE[15:], blocked=True) == []
    manifest = _manifest(tmp_path)
    assert manifest[_GONE]["missed"] == 1
    assert all(manifest[url]["missed"] == 0 for url in _SITE[1:])


def test_too_many_missing_pages_are_not_removed(tmp_path):
    _uscis_crawl(tmp_path, _SITE)
    _uscis_crawl(tmp_path, _SITE[5:])  # five pages missed once: plausible so far

    # Still missing: removing five of thirty at once is past the cap, which is
    # what a redesign that hides the links would look like. Nothing is removed
    # and the counts stay put, so the crawl after a fix decides.
    assert _uscis_crawl(tmp_path, _SITE[5:]) == []
    manifest = _manifest(tmp_path)
    assert all(manifest[url]["missed"] == 1 for url in _SITE[:5])

    # Every later crawl refuses in the same way, until someone who checked that
    # the pages are gone lets one crawl through. A crawl after that is clean.
    assert _uscis_crawl(tmp_path, _SITE[5:]) == []
    assert _uscis_crawl(tmp_path, _SITE[5:], allow_large_removal="1") == _SITE[:5]
    assert set(_manifest(tmp_path)) == set(_SITE[5:])
    assert _uscis_crawl(tmp_path, _SITE[5:]) == []


def test_manifest_from_before_miss_counts_still_loads(tmp_path):
    digest = hashlib.sha256(b"<p>same every week</p>").hexdigest()
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests" / "uscis.json").write_text(
        json.dumps({url: digest for url in _SITE})
    )

    # Nothing is re-emitted (every page is recognised as unchanged), and the
    # page that is absent starts counting from zero.
    assert _uscis_crawl(tmp_path, _SITE[1:]) == []
    manifest = _manifest(tmp_path)
    assert manifest[_GONE] == {"hash": digest, "missed": 1}
    assert manifest[_SITE[1]] == {"hash": digest, "missed": 0}
