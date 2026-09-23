"""Download the crawl's JSONL feeds from R2 for `manage.py ingest_scrape`.

    python pull_feeds.py [dest]     # default dest: output/items/uscis

Fetches every raw/items/uscis/*.jsonl not already present in dest (feeds are
immutable per crawl, so an existing file is skipped). Reads R2_BUCKET and the
AWS_* credentials from config/.env, the same ones the crawl writes with.
"""
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "config" / ".env")

PREFIX = "raw/items/uscis/"


def main(dest: Path) -> None:
    bucket = os.environ["R2_BUCKET"]
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.getenv("AWS_REGION_NAME") or "auto",
    )
    dest.mkdir(parents=True, exist_ok=True)
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            target = dest / obj["Key"].rsplit("/", 1)[-1]
            if target.exists() and target.stat().st_size == obj["Size"]:
                print(f"have {target.name}")
                continue
            print(f"pull {target.name} ({obj['Size'] / 1e6:.1f} MB)")
            s3.download_file(bucket, obj["Key"], str(target))
    print(f"feeds in {dest.resolve()}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/items/uscis"))
