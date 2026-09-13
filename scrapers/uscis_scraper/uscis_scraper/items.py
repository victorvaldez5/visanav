import scrapy
from itemloaders.processors import TakeFirst


class UscisItem(scrapy.Item):
    url = scrapy.Field(output_processor=TakeFirst())
    content_type = scrapy.Field(output_processor=TakeFirst())
    content = scrapy.Field(output_processor=TakeFirst())
    parent_page = scrapy.Field(output_processor=TakeFirst())
    file_urls = scrapy.Field()
    files = scrapy.Field()
    # sha256 of `content`, stamped by ContentHashPipeline so downstream ingest
    # can tell which HTML pages actually changed between crawls.
    content_hash = scrapy.Field(output_processor=TakeFirst())
