"""Where `ingest_scrape` gets the scrapers' feeds from.

A feed store answers two questions per source: what is the newest feed (cheap,
used to decide whether the source is due), and give me every feed (crawls are
incremental, so a snapshot needs them all). `LocalFeeds` reads a feeds root on
disk, as pulled by scrapers/uscis_scraper/pull_feeds.py or written by a
LOCAL_TEST crawl. `R2Feeds` reads the bucket the scheduled crawls write to.
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class LocalFeeds:
    """A feeds root: one subdirectory of *.jsonl feeds per source."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def newest(self, source: str) -> str | None:
        paths = self.fetch(source)
        return paths[-1].name if paths else None

    def fetch(self, source: str) -> list[Path]:
        return sorted((self.root / source).glob("*.jsonl"), key=lambda p: p.name)


class R2Feeds:
    """The crawls' feeds in R2 (raw/items/<source>/*.jsonl), downloaded on demand."""

    PREFIX = "raw/items/"

    def __init__(self, bucket: str, client, workdir: Path):
        self.bucket = bucket
        self.client = client
        self.workdir = Path(workdir)

    @classmethod
    def from_settings(cls, workdir: Path) -> "R2Feeds":
        missing = [
            name
            for name in ("R2_BUCKET", "AWS_ENDPOINT_URL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
            if not getattr(settings, name)
        ]
        if missing:
            raise ImproperlyConfigured(f"Reading feeds from R2 needs {', '.join(missing)}")
        try:
            import boto3
        except ImportError as exc:  # the web image deliberately ships without it
            raise ImproperlyConfigured(
                "Reading feeds from R2 needs boto3: use the ingest image "
                "(api/ingest.Dockerfile) or `uv sync --group ingest`"
            ) from exc
        # Under dev settings the root logger is at DEBUG, and botocore then logs
        # every request it signs. Nothing in those lines helps an ingest run.
        for noisy in ("boto3", "botocore", "s3transfer", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION_NAME,
        )
        return cls(settings.R2_BUCKET, client, workdir)

    def _objects(self, source: str) -> list[dict]:
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=f"{self.PREFIX}{source}/"
        )
        feeds = [
            obj for page in pages for obj in page.get("Contents", [])
            if obj["Key"].endswith(".jsonl")
        ]
        return sorted(feeds, key=lambda obj: obj["Key"])

    def newest(self, source: str) -> str | None:
        feeds = self._objects(source)
        return feeds[-1]["Key"].rsplit("/", 1)[-1] if feeds else None

    def fetch(self, source: str) -> list[Path]:
        target_dir = self.workdir / source
        target_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for obj in self._objects(source):
            target = target_dir / obj["Key"].rsplit("/", 1)[-1]
            self.client.download_file(self.bucket, obj["Key"], str(target))
            paths.append(target)
        return paths
