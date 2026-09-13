###############################################################################
# 1) BUILDER: install build-deps & build wheels
###############################################################################
FROM python:3.13-slim AS builder

# install system packages needed to compile wheels (e.g. lxml, cryptography, ...)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      libxml2-dev \
      libxslt1-dev \
      libffi-dev \
      libssl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy your main requirements
COPY ./scrapers/uscis_scraper/requirements.txt .

# build wheels into /wheels
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels \
       -r requirements.txt
###############################################################################
# 2) DEVELOPMENT: inherits from builder, adds dev-dependencies & drops to shell
###############################################################################
FROM builder AS development

# when we have a separate requirements-dev.txt, copy & install it
# COPY requirements-dev.txt ./
# RUN pip install --no-cache-dir -r requirements-dev.txt

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir /wheels/*.whl

# by default land in a shell, mount your code locally to /app
CMD ["scrapy", "crawl", "uscis"]

###############################################################################
# 3) PRODUCTION: runtime image with only minimal OS libs & your wheels
###############################################################################
FROM python:3.13-slim AS production

# install only the runtime OS libs needed for your wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libxml2 \
      libxslt1.1 \
      libffi8 \
      libssl3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy built wheels from the builder stage
COPY --from=builder /wheels /wheels

# install them
RUN pip install --no-cache-dir /wheels/*.whl

# copy your actual scraper code
COPY scrapers/uscis_scraper/ .

# default to running your crawl
CMD ["scrapy", "crawl", "uscis"]
