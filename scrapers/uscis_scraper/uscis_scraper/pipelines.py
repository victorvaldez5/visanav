import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from readability import Document
from scrapy import Request
from scrapy.exceptions import NotConfigured, DropItem
from scrapy.pipelines.files import FilesPipeline


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
        if item.get("content_type") != "text/html":
            return item

        html = item.get("content", "")
        if not html:
            raise DropItem("No HTML content found")

        # use readability to extract the main article and title
        return item


class HTMLPagesPipeline:
    """Persist each HTML page's raw content.

    In local mode (``LOCAL_TEST``) pages are written under ``<local_dir>/html``.
    In production the same bytes are uploaded to Cloudflare R2 (S3-compatible)
    at ``raw/html/<path>.html``.
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
        # only act on HTML items
        if item.get("content_type") != "text/html":
            return item

        item_url = item.get("url")
        html_bytes = item.get("content", "").encode("utf-8")
        path = urlparse(item_url).path.lstrip("/")

        if ".xhtml" in item_url:
            path = f"{urlparse(item_url).netloc}/{item_url.split('?')[-1].split(':')[-1].split('&')[0]}"
        if not path:
            path = "root"

        if self.local_test:
            # save under <local_dir>/html/<path>.html
            file_path = os.path.join(self.local_dir, "html", f"{path}.html")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(html_bytes)
        else:
            # upload to s3://<bucket>/raw/html/<path>.html
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=f"raw/html/{path}.html",
                Body=html_bytes,
                ContentType="text/html",
            )

        return item


class ContentHashPipeline:
    """Skip HTML pages whose content is unchanged since the last crawl.

    Keeps a manifest ``{url: sha256(content)}`` alongside the scraped output (a
    local file in ``LOCAL_TEST`` mode, ``raw/manifest.json`` in R2). On a
    scheduled re-run, an item whose hash matches the manifest is dropped before
    it reaches the storage/feed sinks, so unchanged pages are neither re-written
    nor forwarded downstream. PDFs rely on the FilesPipeline's own store-level
    dedup and pass through untouched.
    """

    MANIFEST_KEY = "raw/manifest.json"
    MANIFEST_NAME = "manifest.json"

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
        self.manifest = {}
        self._dirty = False

    def open_spider(self, spider):
        self.manifest = self._load_manifest()

    def close_spider(self, spider):
        if self._dirty:
            self._save_manifest()

    def process_item(self, item, spider):
        # Only HTML carries `content` to hash; PDFs pass straight through.
        if item.get("content_type") != "text/html":
            return item

        url = item.get("url")
        digest = hashlib.sha256(item.get("content", "").encode("utf-8")).hexdigest()
        if url and self.manifest.get(url) == digest:
            raise DropItem(f"unchanged: {url}")

        self.manifest[url] = digest
        self._dirty = True
        item["content_hash"] = digest
        return item

    # -- manifest persistence -------------------------------------------------

    @property
    def _local_path(self):
        return os.path.join(self.local_dir, self.MANIFEST_NAME)

    def _load_manifest(self):
        """Return the stored manifest, or an empty dict on the first run."""
        try:
            if self.local_test:
                with open(self._local_path, encoding="utf-8") as f:
                    return json.load(f)
            resp = self.s3_client.get_object(Bucket=self.bucket, Key=self.MANIFEST_KEY)
            return json.loads(resp["Body"].read())
        except FileNotFoundError:
            return {}
        except Exception:
            # Missing (e.g. S3 NoSuchKey) or unreadable manifest: a missing
            # manifest must never fail the crawl — start fresh (everything is
            # treated as new for this run).
            return {}

    def _save_manifest(self):
        payload = json.dumps(self.manifest, sort_keys=True).encode("utf-8")
        if self.local_test:
            os.makedirs(self.local_dir, exist_ok=True)
            with open(self._local_path, "wb") as f:
                f.write(payload)
        else:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self.MANIFEST_KEY,
                Body=payload,
                ContentType="application/json",
            )


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
