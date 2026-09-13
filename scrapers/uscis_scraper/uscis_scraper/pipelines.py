import os
import re
from pathlib import Path
from urllib.parse import urlparse

import boto3
from readability import Document
from scrapy import Request
from scrapy.exceptions import NotConfigured, DropItem
from scrapy.pipelines.files import FilesPipeline


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
    """Upload each HTML page’s raw content to S3 (or save locally)."""

    @classmethod
    def from_crawler(cls, crawler):
        bucket = crawler.settings.get("AWS_S3_BUCKET")
        local_test = crawler.settings.get("LOCAL_TEST")
        local_dir = crawler.settings.get("LOCAL_FILES")

        if bucket is None or local_test is None:
            raise NotConfigured("Missing AWS_S3_BUCKET or LOCAL_TEST in settings")

        # only initialize an S3 client if we’re actually pushing to S3
        s3_client = None
        if not local_test:
            aws_key = crawler.settings.get("AWS_ACCESS_KEY_ID")
            aws_secret = crawler.settings.get("AWS_SECRET_ACCESS_KEY")
            aws_region = crawler.settings.get("AWS_REGION")
            session = boto3.Session(
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                region_name=aws_region,
            )
            s3_client = session.client("s3")

        return cls(bucket, s3_client, local_test, local_dir)

    def __init__(self, bucket, s3_client, local_test, local_dir):
        self.bucket = bucket
        self.s3_client = s3_client
        self.local_test = local_test
        self.local_dir = local_dir

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
            # save under local_files/page.html
            file_path = os.path.join(self.local_dir, "html", f"{path}.html")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(html_bytes)
        else:
            # upload to s3://<bucket>/html/<parent>/<path>.html
            key = f"raw/html/{path}.html"
            self.s3_client.put_object(
                Bucket=self.bucket, Key=key, Body=html_bytes, ContentType="text/html"
            )

        return item


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
