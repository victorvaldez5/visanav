# Scrapy settings for uscis_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
BOT_NAME = "uscis_scraper"

SPIDER_MODULES = ["uscis_scraper.spiders"]
NEWSPIDER_MODULE = "uscis_scraper.spiders"

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "uscis-scraper-dev")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Local Test Settings
LOCAL_TEST = os.getenv("LOCAL_TEST", "True").lower() in ("1", "true", "yes")
LOCAL_SIZE_LIMIT_MB = os.getenv("LOCAL_SIZE_LIMIT_MB", 10)
LOCAL_FILES = os.getenv("LOCAL_FILES", "output")


ADDONS = {}
# Feed export
if not LOCAL_TEST:
    FEED_URI = f"s3://{AWS_S3_BUCKET}/raw/items/%(name)s/%(time)s.jsonl"
    FEED_FORMAT = "jsonlines"
    FEED_EXPORT_ENCODING = "utf-8"
    FILES_STORE = f"s3://{AWS_S3_BUCKET}/raw/"
    ROBOTSTXT_OBEY = True
    DOWNLOAD_DELAY = 5
    CONCURRENT_REQUESTS = 8
    AUTOTHROTTLE_ENABLED = True
    # The initial download delay
    AUTOTHROTTLE_START_DELAY = 2
    # The maximum download delay to be set in case of high latencies
    AUTOTHROTTLE_MAX_DELAY = 30

    AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

    # Retry middleware settings
    RETRY_ENABLED = True
    RETRY_TIMES = 3
else:
    FEED_URI = f"{LOCAL_FILES}/items/%(name)s/%(time)s.jsonl"
    FEED_FORMAT = "jsonlines"
    FEED_EXPORT_ENCODING = "utf-8"
    FILES_STORE = os.getenv("LOCAL_FILES", "output")
logger.warning(
    f"**Scrapy Settings** → LOCAL_TEST={LOCAL_TEST}, FILES_STORE={FILES_STORE}"
)
# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "uscis-scraper (+https://github.com/victorvaldez5)"

# Logging
DUPEFILTER_CLASS = "scrapy.dupefilters.BaseDupeFilter"

# Logging
LOG_LEVEL = "INFO"
LOGSTATS_INTERVAL = 10  # print stats every 10 seconds
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_STDOUT = True

# Default headers (helps avoid being blocked)
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Item pipelines
ITEM_PIPELINES = {
    "uscis_scraper.pipelines.CleanValidatePipeline": 91,
    "uscis_scraper.pipelines.HTMLPagesPipeline": 100,
    "uscis_scraper.pipelines.NamedFilesPipeline": 200,
}

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0
# HTTPCACHE_DIR = "httpcache"
# HTTPCACHE_IGNORE_HTTP_CODES = []
# HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"
