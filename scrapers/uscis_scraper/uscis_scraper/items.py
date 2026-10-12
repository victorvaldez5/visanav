import scrapy
from itemloaders.processors import TakeFirst


class ScrapedItem(scrapy.Item):
    """One page, document or file from any source (the spider's name says which)."""

    url = scrapy.Field(output_processor=TakeFirst())
    content_type = scrapy.Field(output_processor=TakeFirst())
    content = scrapy.Field(output_processor=TakeFirst())
    parent_page = scrapy.Field(output_processor=TakeFirst())
    file_urls = scrapy.Field()
    files = scrapy.Field()
    # sha256 of `content` (of `spider.stable_content(content)` when the spider
    # defines it), stamped by ContentHashPipeline so downstream ingest can tell
    # which pages actually changed between crawls.
    content_hash = scrapy.Field(output_processor=TakeFirst())
    # Structured fields the source's ingest extractor needs (citation, document
    # type, publication date, ...). Free-form per source.
    meta = scrapy.Field(output_processor=TakeFirst())
    # True on a tombstone: the URL no longer exists at the source, so ingest
    # must drop it from the merged snapshot. Carries no content.
    removed = scrapy.Field(output_processor=TakeFirst())
