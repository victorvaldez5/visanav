import os
import re
from pathlib import Path
from urllib.parse import urlparse

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
    """Save each HTML page's raw content to the local files store.

    The S3 upload sink was removed during the AWS teardown. To ship scraped
    pages to a production store, add a remote sink here (e.g. a Fly volume or
    an S3-compatible object store) instead of writing under ``local_dir``.
    """

    @classmethod
    def from_crawler(cls, crawler):
        local_dir = crawler.settings.get("LOCAL_FILES")
        if not local_dir:
            raise NotConfigured("Missing LOCAL_FILES in settings")
        return cls(local_dir)

    def __init__(self, local_dir):
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

        # save under <local_dir>/html/<path>.html
        file_path = os.path.join(self.local_dir, "html", f"{path}.html")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(html_bytes)

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
