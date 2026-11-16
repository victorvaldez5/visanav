"""The R2 (S3-compatible) client the crawls write with, and a live check of it.

`check_endpoint_url` runs before every R2 crawl (commands/crawl.py), and
`scrapy r2_check` (commands/r2_check.py) proves the credentials can write,
read back and delete an object, then lists each spider's feeds.
"""
from __future__ import annotations

import uuid
from urllib.parse import urlparse

# Where the crawls' JSONL feeds land, one directory per spider (settings.FEED_URI).
FEEDS_PREFIX = "raw/items/"
# The probe object r2_check writes and deletes again.
PROBE_PREFIX = "raw/healthcheck/"


class R2ConfigError(ValueError):
    """R2 settings that cannot work, found before any request is made."""


def check_endpoint_url(url: str | None) -> None:
    """Refuse an R2 endpoint that is anything but the account URL.

    The endpoint is https://<account>.r2.cloudflarestorage.com and the bucket is
    R2_BUCKET. With the bucket on the end of the URL as well, botocore takes that
    path segment for the bucket and the real key gets the bucket name in front,
    so uploads land where nothing reads them and listings fail with NoSuchKey.
    """
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise R2ConfigError(
            "AWS_ENDPOINT_URL must be a URL like https://<account>.r2.cloudflarestorage.com"
        )
    if parsed.path.strip("/") or parsed.query or parsed.fragment:
        raise R2ConfigError(
            f"AWS_ENDPOINT_URL must be the account endpoint alone, without the path "
            f"{parsed.path!r}: put the bucket name in R2_BUCKET, not in the URL"
        )


def check_settings(settings) -> None:
    """Everything an R2 crawl needs, checked up front."""
    missing = [
        name
        for name in ("R2_BUCKET", "AWS_ENDPOINT_URL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
        if not settings.get(name)
    ]
    if missing:
        raise R2ConfigError(f"writing to R2 needs {', '.join(missing)}")
    check_endpoint_url(settings.get("AWS_ENDPOINT_URL"))


def build_s3_client(settings):
    """Create a botocore S3 client pointed at the configured endpoint (Cloudflare R2).

    Imported lazily so local-mode crawls and unit tests never need botocore.
    """
    import botocore.session

    check_endpoint_url(settings.get("AWS_ENDPOINT_URL"))
    session = botocore.session.get_session()
    return session.create_client(
        "s3",
        endpoint_url=settings.get("AWS_ENDPOINT_URL"),
        aws_access_key_id=settings.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=settings.get("AWS_SECRET_ACCESS_KEY"),
        region_name=settings.get("AWS_REGION_NAME") or "auto",
    )


def newest_feed(client, bucket: str, spider: str) -> str | None:
    """The newest feed's file name under raw/items/<spider>/, or None."""
    names = []
    for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=f"{FEEDS_PREFIX}{spider}/"
    ):
        names += [obj["Key"].rsplit("/", 1)[-1] for obj in page.get("Contents", [])
                  if obj["Key"].endswith(".jsonl")]
    return max(names) if names else None


def probe(client, bucket: str) -> str:
    """Write, read back and delete one small object; return its key.

    Raises on any failed step. The object is deleted even when the read fails.
    """
    key = f"{PROBE_PREFIX}{uuid.uuid4().hex}.txt"
    body = b"r2_check\n"
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/plain")
    try:
        read = client.get_object(Bucket=bucket, Key=key)["Body"].read()
        if read != body:
            raise RuntimeError(f"read back {len(read)} bytes from {key}, wrote {len(body)}")
    finally:
        client.delete_object(Bucket=bucket, Key=key)
    return key
