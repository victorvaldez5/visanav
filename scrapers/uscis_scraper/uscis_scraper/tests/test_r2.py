from urllib.parse import urlsplit

import pytest
from scrapy.settings import Settings

from ..r2 import (
    R2ConfigError, build_s3_client, check_endpoint_url, check_settings, newest_feed, probe,
)


def _settings(**overrides):
    values = {
        "R2_BUCKET": "visanav-test",
        "AWS_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com",
        "AWS_ACCESS_KEY_ID": "test-key-id",
        "AWS_SECRET_ACCESS_KEY": "test-secret",
        "AWS_REGION_NAME": "auto",
    }
    values.update(overrides)
    return Settings(values)


class _Sent(Exception):
    """Raised from botocore's before-send hook, so nothing leaves the machine."""


def test_uploads_go_to_the_bucket_the_settings_name():
    """The real botocore client: a feed upload is addressed to R2_BUCKET under the
    account endpoint, with the key exactly as the pipeline gives it."""
    client = build_s3_client(_settings())
    sent = []

    def capture(request, **kwargs):
        sent.append(request.url)
        raise _Sent

    client.meta.events.register("before-send.s3.PutObject", capture)
    with pytest.raises(_Sent):
        client.put_object(Bucket="visanav-test", Key="raw/items/ecfr/feed.jsonl", Body=b"x")

    url = urlsplit(sent[0])
    assert (url.scheme, url.netloc, url.path) == (
        "https", "account.r2.cloudflarestorage.com", "/visanav-test/raw/items/ecfr/feed.jsonl",
    )


@pytest.mark.parametrize("endpoint", [
    "https://account.r2.cloudflarestorage.com/visanav-test",
    "https://account.r2.cloudflarestorage.com/visanav-test/",
    "account.r2.cloudflarestorage.com",
    None,
])
def test_an_endpoint_that_is_not_the_account_url_is_refused(endpoint):
    with pytest.raises(R2ConfigError, match="AWS_ENDPOINT_URL"):
        check_endpoint_url(endpoint)
    with pytest.raises(R2ConfigError):
        build_s3_client(_settings(AWS_ENDPOINT_URL=endpoint))


def test_the_account_url_is_accepted():
    check_endpoint_url("https://account.r2.cloudflarestorage.com")
    check_endpoint_url("https://account.r2.cloudflarestorage.com/")
    check_settings(_settings())


def test_missing_r2_settings_are_named():
    with pytest.raises(R2ConfigError, match="R2_BUCKET, AWS_SECRET_ACCESS_KEY"):
        check_settings(_settings(R2_BUCKET="", AWS_SECRET_ACCESS_KEY=None))


class _FakeS3:
    def __init__(self, objects=None, corrupt_reads=False):
        self.objects = dict(objects or {})
        self.corrupt_reads = corrupt_reads

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        data = b"" if self.corrupt_reads else self.objects[Key]
        return {"Body": type("Body", (), {"read": lambda self: data})()}

    def delete_object(self, Bucket, Key):
        del self.objects[Key]

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        objects = self.objects

        class _Paginator:
            def paginate(self, Bucket, Prefix):
                keys = sorted(k for k in objects if k.startswith(Prefix))
                yield {"Contents": [{"Key": k} for k in keys[:1]]}
                yield {}

        return _Paginator()


def test_probe_writes_reads_and_deletes_one_object():
    s3 = _FakeS3({"raw/items/ecfr/a.jsonl": b"keep"})
    key = probe(s3, "visanav-test")
    assert key.startswith("raw/healthcheck/")
    assert s3.objects == {"raw/items/ecfr/a.jsonl": b"keep"}


def test_probe_fails_and_cleans_up_when_the_read_differs():
    s3 = _FakeS3(corrupt_reads=True)
    with pytest.raises(RuntimeError, match="read back 0 bytes"):
        probe(s3, "visanav-test")
    assert s3.objects == {}


def test_newest_feed_is_per_spider_and_ignores_other_files():
    s3 = _FakeS3({
        "raw/items/ecfr/2026-11-02T09-00-00+00-00.jsonl": b"",
        "raw/items/ecfr/notes.txt": b"",
        "raw/items/ecfr-archive/2027-01-01T00-00-00+00-00.jsonl": b"",
    })
    assert newest_feed(s3, "visanav-test", "ecfr") == "2026-11-02T09-00-00+00-00.jsonl"
    assert newest_feed(s3, "visanav-test", "uscis") is None
