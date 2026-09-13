import scrapy
from itemloaders.processors import TakeFirst


class UscisItem(scrapy.Item):
    url = scrapy.Field(output_processor=TakeFirst())
    content_type = scrapy.Field(output_processor=TakeFirst())
    content = scrapy.Field(output_processor=TakeFirst())
    parent_page = scrapy.Field(output_processor=TakeFirst())
    file_urls = scrapy.Field()
    files = scrapy.Field()
