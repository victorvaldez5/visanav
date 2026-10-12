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
from pathlib import Path

from dotenv import load_dotenv

# Environment lives in the repo-root config/ directory (see config/.env.example).
# settings.py is at scrapers/uscis_scraper/uscis_scraper/, so the repo root is
# three levels up. In the Docker image the code sits at /app/uscis_scraper/, too
# shallow for that walk, and compose injects config/.env via env_file instead.
_parents = Path(__file__).resolve().parents
if len(_parents) > 3:
    load_dotenv(_parents[3] / "config" / ".env")
logger = logging.getLogger(__name__)
BOT_NAME = "uscis_scraper"

SPIDER_MODULES = ["uscis_scraper.spiders"]
NEWSPIDER_MODULE = "uscis_scraper.spiders"
# Overrides `scrapy crawl` so an untrustworthy crawl exits non-zero (health.py).
COMMANDS_MODULE = "uscis_scraper.commands"

# Local Test Settings
LOCAL_TEST = os.getenv("LOCAL_TEST", "True").lower() in ("1", "true", "yes")
LOCAL_SIZE_LIMIT_MB = os.getenv("LOCAL_SIZE_LIMIT_MB", 10)
LOCAL_FILES = os.getenv("LOCAL_FILES", "output")

# Cloudflare R2 (S3-compatible) object store for production crawls. When
# LOCAL_TEST is false, scraped HTML/PDF/JSONL is written here instead of the
# local `output/` dir. These AWS_* names are the ones Scrapy's built-in S3 feed
# export and FilesPipeline read, so defining them wires the PDF + JSONL sinks;
# the custom HTMLPagesPipeline and ContentHashPipeline read the same values.
R2_BUCKET = os.getenv("R2_BUCKET")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.getenv("AWS_REGION_NAME", "auto")
# Force SSL for the S3 client. Scrapy's AWS_USE_SSL defaults to None, and with
# use_ssl=None botocore's S3 region-redirector infinitely recurses against R2
# (a HeadObject 404 is misread as a region redirect -> HeadBucket -> loop).
# Setting it True makes S3FilesStore build a working client. See settings docs.
AWS_USE_SSL = True


ADDONS = {}
# Feed export. Production writes to Cloudflare R2 (needs R2_BUCKET + AWS_* creds
# above); local mode writes under LOCAL_FILES.
if not LOCAL_TEST:
    FEED_URI = f"s3://{R2_BUCKET}/raw/items/%(name)s/%(time)s.jsonl"
    FEED_FORMAT = "jsonlines"
    FEED_EXPORT_ENCODING = "utf-8"
    FILES_STORE = f"s3://{R2_BUCKET}/raw/"
else:
    FEED_URI = f"{LOCAL_FILES}/items/%(name)s/%(time)s.jsonl"
    FEED_FORMAT = "jsonlines"
    FEED_EXPORT_ENCODING = "utf-8"
    FILES_STORE = os.getenv("LOCAL_FILES", "output")

# Politeness applies to every crawl: a LOCAL_TEST run only changes where the
# output goes, it still hits the real government sites (from your own IP). For a
# quick local experiment, shorten the delay with `-s DOWNLOAD_DELAY=1`.
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
logger.warning(
    f"**Scrapy Settings** → LOCAL_TEST={LOCAL_TEST}, FILES_STORE={FILES_STORE}"
)
# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "uscis-scraper (+https://github.com/victorvaldez5)"

# Use Scrapy's default RFPDupeFilter (URL-level dedup) rather than the no-op
# BaseDupeFilter, so the same page linked from multiple places isn't re-fetched
# within a run (the Policy Manual TOC links repeat across pages).

# Logging
LOG_LEVEL = "INFO"
LOGSTATS_INTERVAL = 10  # print stats every 10 seconds
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_STDOUT = True

# Default headers (helps avoid being blocked)
# (User-Agent comes from USER_AGENT, which a spider may override in its
# custom_settings; a default header here would win over that.)
DEFAULT_REQUEST_HEADERS = {
    "Accept-Language": "en",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Item pipelines
ITEM_PIPELINES = {
    "uscis_scraper.pipelines.CleanValidatePipeline": 91,
    "uscis_scraper.pipelines.ContentHashPipeline": 95,
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
