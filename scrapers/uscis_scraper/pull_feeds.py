"""Download the crawls' JSONL feeds from R2 for `manage.py ingest_scrape`.

    python pull_feeds.py                    # every source found in the bucket
    python pull_feeds.py ecfr               # only these sources
    python pull_feeds.py --dest some/dir    # default dest: output/items

Mirrors raw/items/<source>/*.jsonl into <dest>/<source>/, the feeds root that
`ingest_scrape` takes. A feed already present is skipped (feeds are immutable
per crawl). Reads R2_BUCKET and the AWS_* credentials from config/.env, the same
ones the crawl writes with.
"""
import argparse
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "config" / ".env")

PREFIX = "raw/items/"


def main(dest: Path, sources: list[str]) -> None:
    bucket = os.environ["R2_BUCKET"]
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.getenv("AWS_REGION_NAME") or "auto",
    )
    paginator = s3.get_paginator("list_objects_v2")
    if not sources:
        # Each source is a "directory" under raw/items/.
        sources = [
            common["Prefix"][len(PREFIX):].strip("/")
            for page in paginator.paginate(Bucket=bucket, Prefix=PREFIX, Delimiter="/")
            for common in page.get("CommonPrefixes", [])
        ]
    for source in sources:
        target_dir = dest / source
        target_dir.mkdir(parents=True, exist_ok=True)
        found = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{PREFIX}{source}/"):
            for obj in page.get("Contents", []):
                found += 1
                target = target_dir / obj["Key"].rsplit("/", 1)[-1]
                if target.exists() and target.stat().st_size == obj["Size"]:
                    print(f"have {source}/{target.name}")
                    continue
                print(f"pull {source}/{target.name} ({obj['Size'] / 1e6:.1f} MB)")
                s3.download_file(bucket, obj["Key"], str(target))
        if not found:
            print(f"no feeds for {source} in the bucket")
    print(f"feeds in {dest.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources", nargs="*", help="sources to pull (default: all)")
    parser.add_argument("--dest", type=Path, default=Path("output/items"))
    args = parser.parse_args()
    main(args.dest, args.sources)
