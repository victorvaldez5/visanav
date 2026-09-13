import os
import pytest
from scrapy import Request
from scrapy.exceptions import NotConfigured, DropItem
from ..pipelines import HTMLPagesPipeline, NamedFilesPipeline


class DummyCrawler:
    def __init__(self, settings):
        self.settings = settings


def test_html_pages_pipeline_not_configured():
    crawler = DummyCrawler({})
    with pytest.raises(NotConfigured):
        HTMLPagesPipeline.from_crawler(crawler)


def test_html_pages_pipeline_local(tmp_path):
    settings = {
        "AWS_S3_BUCKET": "test-bucket",
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


def test_html_pages_pipeline_s3(monkeypatch):
    calls = {}

    class DummyClient:
        def put_object(self, **kwargs):
            calls.update(kwargs)

    bucket = "buck"
    client = DummyClient()
    pipeline = HTMLPagesPipeline(bucket, client, local_test=False, local_dir=None)

    item = {
        "url": "https://host/example.html",
        "content_type": "text/html",
        "content": "XYZ",
    }
    out = pipeline.process_item(item, spider=None)
    assert out is item

    # code builds Key="html/<path>.html"
    assert calls["Bucket"] == bucket
    assert calls["Key"] == "html/example.html.html"
    assert calls["Body"] == b"XYZ"
    assert calls["ContentType"] == "text/html"


def test_named_files_pipeline_requests_and_path():
    pipe = NamedFilesPipeline(store_uri="unused")
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

    # test file_path naming
    fake = Request("http://foo/x/y.pdf", meta={"parent_page": item["parent_page"]})
    out_path = pipe.file_path(fake)
    assert out_path == os.path.join("pdf", "y.pdf")


@pytest.fixture
def html_item():
    return {
        "url": "https://example.com/some/path",
        "content_type": "text/html",
        "content": "<h1>OK</h1>",
    }


def test_html_pipeline_skips_non_html(tmp_path, html_item):
    settings = {"AWS_S3_BUCKET": "b", "LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
    pipeline = HTMLPagesPipeline.from_crawler(DummyCrawler(settings))

    pdf_item = dict(html_item, content_type="application/pdf")
    out = pipeline.process_item(pdf_item, spider=None)
    # Should simply return the item without writing any file
    assert out is pdf_item
    assert not (tmp_path / "html").exists()


def test_html_pipeline_root_fallback(tmp_path):
    settings = {"AWS_S3_BUCKET": "b", "LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
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
    settings = {"AWS_S3_BUCKET": "b", "LOCAL_TEST": True, "LOCAL_FILES": str(tmp_path)}
    pipeline = HTMLPagesPipeline.from_crawler(DummyCrawler(settings))

    # simulate an .xhtml URL with query params & fragments
    url = "https://host/doc.xhtml?req=granuleid:USC-prelim-title8-section1101&num=0&edition=prelim"
    item = {"url": url, "content_type": "text/html", "content": "<p>XHTML</p>"}
    pipeline.process_item(item, spider=None)
    # should write under <netloc>/<last‐param>.html, e.g. host/section=5.html
    # splitting logic takes 'section=5' as key
    expected = tmp_path / "html" / f"host/USC-prelim-title8-section1101.html"
    assert expected.exists()
    assert "XHTML" in expected.read_text()


def test_html_pipeline_xhtml_s3(monkeypatch):
    calls = {}

    class DummyClient:
        def put_object(self, **kw):
            calls.update(kw)

    # bypass from_crawler, instantiate directly for S3 mode
    bucket = "BUCK"
    pipeline = HTMLPagesPipeline(
        bucket, DummyClient(), local_test=False, local_dir=None
    )

    url = "https://h/doc.xhtml?req=granuleid:USC-prelim-title8-section1101&num=0&edition=prelim"
    item = {"url": url, "content_type": "text/html", "content": "C"}
    pipeline.process_item(item, spider=None)

    # key should be "html/h/foo.html"
    assert calls["Bucket"] == bucket
    assert calls["Key"] == "html/h/USC-prelim-title8-section1101.html"
    assert calls["ContentType"] == "text/html"
    assert calls["Body"] == b"C"


def test_named_files_pipeline_no_urls():
    pipe = NamedFilesPipeline(store_uri="unused")
    # item without file_urls or empty list
    for itm in ({}, {"file_urls": []}):
        reqs = list(pipe.get_media_requests(itm, info=None))
        assert reqs == []


def test_named_files_pipeline_uncategorized_path():
    pipe = NamedFilesPipeline(store_uri="u")
    # missing parent_page → 'uncategorized'
    req = Request("http://x.com/a.pdf", meta={})
    path = pipe.file_path(req)
    assert path == os.path.join("pdf", "a.pdf")


def test_named_files_pipeline_multiple_requests():
    pipe = NamedFilesPipeline(store_uri="dummy://")
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
    pipe = NamedFilesPipeline(store_uri="dummy://")
    # a deeply nested parent_page path
    parent = "https://site.com/a/b/c/d"
    req = Request("http://cdn.com/doc.pdf", meta={"parent_page": parent})
    out = pipe.file_path(req)
    # expect each segment to become a folder under 'pdf/'
    expected = os.path.join("pdf", "doc.pdf")
    assert out == expected


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
    pipe = NamedFilesPipeline(store_uri="dummy://")
    req = Request(url, meta={"parent_page": "https://host/"})
    path = pipe.file_path(req)
    # split the returned path
    segments = path.split(os.sep)
    # first segment is 'pdf', second is 'uncategorized'
    assert segments[0] == "pdf"
    # last segment matches expected basename (might be empty string)
    assert segments[-1] == expected_name
