import hashlib
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from scrapy import Request, signals
from scrapy.exceptions import NotConfigured, DropItem
from scrapy.pipelines.files import FilesPipeline

from .health import feed_was_stored


# The first source. Its raw pages and (as a fallback) its manifest keep their
# original un-namespaced keys; every later source is namespaced by spider name.
LEGACY_SOURCE = "uscis"

# Page content types the raw-page sink stores, and the extension each gets.
_PAGE_EXTENSIONS = {"text/html": "html", "application/xml": "xml"}


logger = logging.getLogger(__name__)


def _source(spider):
    return getattr(spider, "name", None) or LEGACY_SOURCE


def _build_s3_client(settings):
    """Create a botocore S3 client pointed at the configured S3-compatible
    endpoint (Cloudflare R2).

    Imported lazily so local-mode crawls and unit tests never need botocore.
    """
    import botocore.session

    session = botocore.session.get_session()
    return session.create_client(
        "s3",
        endpoint_url=settings.get("AWS_ENDPOINT_URL"),
        aws_access_key_id=settings.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=settings.get("AWS_SECRET_ACCESS_KEY"),
        region_name=settings.get("AWS_REGION_NAME") or "auto",
    )


class CleanValidatePipeline:
    """Cleans and validates item URLs and paths, dropping invalid items."""

    def process_item(self, item, spider):
        # PDFs carry file_urls and tombstones carry nothing; every other item
        # is a page and must have content.
        if item.get("removed") or item.get("content_type") not in _PAGE_EXTENSIONS:
            return item

        if not item.get("content"):
            raise DropItem("No page content found")

        return item


class HTMLPagesPipeline:
    """Persist each page's raw content (HTML, or XML for sources that serve it).

    In local mode (``LOCAL_TEST``) pages are written under ``<local_dir>``; in
    production the same bytes are uploaded to Cloudflare R2 (S3-compatible)
    under ``raw/``. USCIS pages keep their original ``html/<path>.html`` keys;
    every other source is namespaced as ``pages/<source>/<path>.<ext>``.
    """

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        local_dir = settings.get("LOCAL_FILES")
        if not local_dir:
            raise NotConfigured("Missing LOCAL_FILES in settings")
        local_test = settings.get("LOCAL_TEST")
        bucket = settings.get("R2_BUCKET")
        s3_client = None
        if not local_test:
            if not bucket:
                raise NotConfigured("LOCAL_TEST is false but R2_BUCKET is unset")
            s3_client = _build_s3_client(settings)
        return cls(local_dir, local_test, bucket, s3_client)

    def __init__(self, local_dir, local_test=True, bucket=None, s3_client=None):
        self.local_dir = local_dir
        self.local_test = local_test
        self.bucket = bucket
        self.s3_client = s3_client

    def process_item(self, item, spider):
        # only act on pages (not PDFs or tombstones)
        content_type = item.get("content_type")
        ext = _PAGE_EXTENSIONS.get(content_type)
        if not ext or item.get("removed"):
            return item

        item_url = item.get("url")
        html_bytes = item.get("content", "").encode("utf-8")
        path = urlparse(item_url).path.lstrip("/")

        if ".xhtml" in item_url:
            path = f"{urlparse(item_url).netloc}/{item_url.split('?')[-1].split(':')[-1].split('&')[0]}"
        if not path:
            path = "root"

        source = _source(spider)
        if source == LEGACY_SOURCE:
            relative = f"html/{path}.html"
        else:
            relative = f"pages/{source}/{path}.{ext}"

        if self.local_test:
            # save under <local_dir>/<relative>
            file_path = os.path.join(self.local_dir, relative)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(html_bytes)
        else:
            # upload to s3://<bucket>/raw/<relative>
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=f"raw/{relative}",
                Body=html_bytes,
                ContentType=content_type,
            )

        return item


class ContentHashPipeline:
    """Skip pages whose content is unchanged since the last crawl.

    Keeps one manifest ``{url: sha256(content)}`` per source alongside the
    scraped output (``manifests/<source>.json``: a local file in ``LOCAL_TEST``
    mode, under ``raw/`` in R2), so crawling one source never touches another's.
    On a scheduled re-run, an item whose hash matches the manifest is dropped
    before it reaches the storage/feed sinks, so unchanged pages are neither
    re-written nor forwarded downstream. PDFs rely on the FilesPipeline's own
    store-level dedup and pass through untouched.

    The hash is taken over ``spider.stable_content(content)`` when the spider
    defines it, so markup that differs on every fetch (random element ids, a
    "current as of" date) does not make an unchanged page look new.

    A page is only recorded once it is safely downstream. The manifest entry is
    written when the item has passed every pipeline and reached the feed
    (``item_scraped``), and the manifest itself is saved only after the feed has
    been stored without error. A page whose raw copy or feed failed to store is
    therefore simply re-emitted by the next crawl, never silently lost.

    The manifest's URLs are published to the spider as ``manifest_urls`` when it
    opens (a spider can skip fetching what it already has, or work out what has
    disappeared). A tombstone item (``removed``) passes through to the feed and
    drops its URL from the manifest.

    Each entry also carries ``missed``: how many healthy crawls in a row did not
    see the page, for spiders that only remove a page once it has stayed away
    (enumeration.MissCountingMixin). The pipeline tells such a spider what it
    saw (``seen_urls``) and the counts so far (``manifest_misses``); the spider
    answers with ``missed_counts`` if the crawl was healthy enough to count, and
    otherwise the stored counts are kept. A manifest written before this (a
    plain ``{url: hash}`` map) still loads, with every count at zero.

    USCIS predates per-source manifests: until its namespaced manifest exists it
    is read from the original shared key, then written namespaced from then on.
    """

    LEGACY_MANIFEST_KEY = "raw/manifest.json"
    LEGACY_MANIFEST_NAME = "manifest.json"

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        local_dir = settings.get("LOCAL_FILES")
        if not local_dir:
            raise NotConfigured("Missing LOCAL_FILES in settings")
        local_test = settings.get("LOCAL_TEST")
        bucket = settings.get("R2_BUCKET")
        s3_client = None
        if not local_test:
            if not bucket:
                raise NotConfigured("LOCAL_TEST is false but R2_BUCKET is unset")
            s3_client = _build_s3_client(settings)
        pipeline = cls(local_dir, local_test, bucket, s3_client)
        pipeline.stats = crawler.stats
        crawler.signals.connect(pipeline.item_scraped, signal=signals.item_scraped)
        if settings.get("FEED_URI") or settings.get("FEEDS"):
            # The feed is stored after the pipelines close, so wait for it.
            pipeline._save_after_feed = True
            crawler.signals.connect(
                pipeline.feed_exporter_closed, signal=signals.feed_exporter_closed
            )
        return pipeline

    def __init__(self, local_dir, local_test=True, bucket=None, s3_client=None):
        self.local_dir = local_dir
        self.local_test = local_test
        self.bucket = bucket
        self.s3_client = s3_client
        self.source = LEGACY_SOURCE
        self.spider = None
        self.manifest = {}  # url -> content hash
        self.misses = {}  # url -> consecutive healthy crawls that did not see it
        self.stats = None
        self._stored = None  # the records as last read from or written to storage
        self._save_after_feed = False

    def open_spider(self, spider):
        self.source = _source(spider)
        self.spider = spider
        self._load_manifest()
        if spider is not None:
            spider.manifest_urls = frozenset(self.manifest)
            spider.manifest_misses = dict(self.misses)

    def close_spider(self, spider):
        if not self._save_after_feed:
            self._save_manifest()

    def feed_exporter_closed(self):
        if not feed_was_stored(self.stats.get_stats() if self.stats else {}):
            logger.error(
                "%s: the feed was not stored, so the manifest is left as it was; "
                "the next crawl will emit this crawl's pages again",
                self.source,
            )
        else:
            self._save_manifest()

    def process_item(self, item, spider):
        # Tombstones and PDFs carry no `content` to hash and pass straight through.
        if item.get("removed") or item.get("content_type") not in _PAGE_EXTENSIONS:
            return item

        url = item.get("url")
        # Seen, whether or not it turns out to have changed.
        seen = getattr(spider, "seen_urls", None)
        if seen is not None:
            seen.add(url)

        content = item.get("content", "")
        stable = getattr(spider, "stable_content", None)
        if callable(stable):
            content = stable(content)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if url and self.manifest.get(url) == digest:
            raise DropItem(f"unchanged: {url}")

        item["content_hash"] = digest
        return item

    def item_scraped(self, item, **kwargs):
        """The item passed every pipeline and was handed to the feed: record it."""
        url = item.get("url")
        if item.get("removed"):
            self.manifest.pop(url, None)
            self.misses.pop(url, None)
        elif item.get("content_hash"):
            self.manifest[url] = item["content_hash"]

    # -- manifest persistence -------------------------------------------------

    @property
    def _relative(self):
        return f"manifests/{self.source}.json"

    @property
    def _local_path(self):
        return os.path.join(self.local_dir, self._relative)

    def _read(self, local_path, key):
        """Return the manifest stored at one location, or None if there is none."""
        try:
            if self.local_test:
                with open(local_path, encoding="utf-8") as f:
                    return json.load(f)
            resp = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read())
        except Exception:
            # Missing (FileNotFoundError, S3 NoSuchKey) or unreadable: a missing
            # manifest must never fail the crawl.
            return None

    def _load_manifest(self):
        """Read the stored manifest into ``manifest`` and ``misses``; both stay
        empty on the first run (everything is then treated as new)."""
        stored = self._read(self._local_path, f"raw/{self._relative}")
        self._stored = stored
        if stored is None and self.source == LEGACY_SOURCE:
            stored = self._read(
                os.path.join(self.local_dir, self.LEGACY_MANIFEST_NAME),
                self.LEGACY_MANIFEST_KEY,
            )
            # self._stored stays None, so it is written back namespaced even if
            # this crawl changes nothing.
        self.manifest, self.misses = {}, {}
        for url, entry in (stored or {}).items():
            # Before miss counts, an entry was just the hash.
            if isinstance(entry, dict):
                self.manifest[url] = entry.get("hash")
                self.misses[url] = entry.get("missed", 0)
            else:
                self.manifest[url] = entry

    def _records(self):
        # A spider that counts misses reports this crawl's counts (seen pages
        # are simply absent, so they reset to zero); None means the crawl was
        # not fit to count, and the stored counts stand.
        counts = getattr(self.spider, "missed_counts", None)
        if counts is None:
            counts = self.misses
        return {
            url: {"hash": digest, "missed": counts.get(url, 0)}
            for url, digest in self.manifest.items()
        }

    def _save_manifest(self):
        records = self._records()
        if records == self._stored or (not records and self._stored is None):
            return
        payload = json.dumps(records, sort_keys=True).encode("utf-8")
        if self.local_test:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "wb") as f:
                f.write(payload)
        else:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=f"raw/{self._relative}",
                Body=payload,
                ContentType="application/json",
            )
        self._stored = records


class NamedFilesPipeline(FilesPipeline):

    def _get_store(self, uri: str):
        scheme = "file" if Path(uri).is_absolute() else urlparse(uri).scheme
        if scheme not in self.STORE_SCHEMES:
            scheme = "file"
        store_cls = self.STORE_SCHEMES[scheme]
        return store_cls(uri)

    def get_media_requests(self, item, info):
        # attach the parent page URL so we can use it in file_path
        for file_url in item.get("file_urls", []):
            yield Request(file_url, meta={"parent_page": item.get("parent_page")})

    def file_path(self, request, response=None, info=None, **kwargs):
        filename = os.path.basename(urlparse(request.url).path)

        # Check if filename contains any of the instruction-related patterns
        instruction_patterns = ["instr", "Instructions", "INS", "m-"]
        is_instruction = any(pattern in filename for pattern in instruction_patterns)

        # Put files in appropriate subdirectories
        subfolder = "instructions" if is_instruction else "forms"
        return os.path.join("pdf", subfolder, filename)
