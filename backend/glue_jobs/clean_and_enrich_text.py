import os
import sys
import io
import re
import uuid
import logging

import nltk

nltk_data_dir = os.getenv("NLTK_DATA", "./dependencies/nltk_data")
nltk.data.path.append(nltk_data_dir)

from nltk.tokenize import sent_tokenize

from bs4 import BeautifulSoup

from pinecone import Pinecone
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, input_file_name, regexp_extract, explode
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, MapType
from dotenv import load_dotenv


def extract_pdf(data_bytes):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data_bytes))

    full_text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            full_text.append(page_text)
    text = "\n".join(full_text)
    return text


def strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ")


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return "".join(c for c in text if c.isprintable())


def chunk_records(
    text: str, category: str = "immigration", lang: str = "en", max_words: int = 200
):
    sentences = sent_tokenize(text)
    chunks = []
    current, count = [], 0

    for sent in sentences:
        words = sent.split()
        if count + len(words) > max_words:
            chunks.append(
                {
                    "_id": str(uuid.uuid4()),
                    "chunk_text": " ".join(current),
                    "category": category,
                    "lang": lang,
                }
            )
            current, count = [], 0
        current.append(sent)
        count += len(words)

    if current:
        chunks.append(
            {
                "_id": str(uuid.uuid4()),
                "chunk_text": " ".join(current),
                "category": category,
                "lang": lang,
            }
        )

    return chunks


def upsert_partition_to_pinecone(rows):
    import os
    import time
    from pinecone import Pinecone
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    load_dotenv()
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX = "project-raul-index"
    PINECONE_NAMESPACE = "uscis"
    SLEEP_BETWEEN_BATCHES = (
        8  # sleep for 8 seconds between batch upserts to avoid limits
    )

    pc = Pinecone(api_key=PINECONE_API_KEY)
    dense_index = pc.Index(PINECONE_INDEX)

    batch = []
    for row in rows:
        fname = row.file_name
        for chunk in row["chunks"]:
            batch.append(
                {
                    "_id": chunk["_id"],
                    "file_name": fname,
                    "chunk_text": chunk["chunk_text"],
                    "category": chunk["category"],
                    "lang": chunk["lang"],
                }
            )

            if len(batch) >= 50:
                logger.info(f"Flushing batch of {len(batch)} to Pinecone")
                start_ts = time.time()
                dense_index.upsert_records(PINECONE_NAMESPACE, batch)
                elapsed = time.time() - start_ts
                logger.info(f"Upsert completed in {elapsed:.2f}s")
                batch = []
                # time.sleep(SLEEP_BETWEEN_BATCHES)
    if batch:
        logger.info(f"Flushing batch of {len(batch)} to Pinecone")
        start_ts = time.time()
        dense_index.upsert_records(PINECONE_NAMESPACE, batch)
        elapsed = time.time() - start_ts
        logger.info(f"Upsert completed in {elapsed:.2f}s")


# --- Schemas ---
# PDF extractor now returns only text
pdf_schema = StringType()
chunk_schema = ArrayType(
    StructType(
        [
            StructField("_id", StringType(), False),
            StructField("chunk_text", StringType(), False),
            StructField("category", StringType(), False),
            StructField("lang", StringType(), False),
        ]
    )
)

# --- Register UDFs ---
extract_udf = udf(extract_pdf, pdf_schema)
clean_html_udf = udf(lambda html: clean_text(strip_html(html)), StringType())
chunk_udf = udf(chunk_records, chunk_schema)

if __name__ == "__main__":
    spark = SparkSession.builder.appName("PDFAndHTMLExtractorAndChunker").getOrCreate()

    # Input paths (recursive)
    pdf_path = "s3://project-raul-dev/raw/pdf/instructions/"
    html_path = "s3://project-raul-dev/raw/html/"

    # Output path
    output_path = "s3://project-raul-dev/pinecone/uscis-index/"

    # 1) Read & extract PDFs
    pdf_df = (
        spark.read.format("binaryFile")
        .option("pathGlobFilter", "*.pdf")
        .option("recursiveFileLookup", "true")
        .load(pdf_path)
        .withColumn("text", extract_udf("content"))
        .select(
            regexp_extract(input_file_name(), r"([^/]+)$", 1).alias("file_name"), "text"
        )
    )

    # 2) Read & clean HTML
    html_df = (
        spark.read.option("recursiveFileLookup", "true")
        .text(html_path)
        .withColumn("file_path", input_file_name())
        .groupBy("file_path")
        .agg({"value": "collect_list"})
        .withColumn(
            "raw_html",
            udf(lambda lines: "\n".join(lines), StringType())("collect_list(value)"),
        )
        .select(
            regexp_extract("file_path", r"([^/]+)$", 1).alias("file_name"), "raw_html"
        )
        .withColumn("text", clean_html_udf("raw_html"))
        .select("file_name", "text")
    )

    # 3) Union
    unified = pdf_df.unionByName(html_df)

    # 4) Chunk & explode
    chunked = unified.withColumn("chunks", chunk_udf("text"))

    # 5) Write
    chunked.write.mode("overwrite").parquet(output_path)

    # 6) Insert into Pinecone
    chunked.repartition(1).foreachPartition(upsert_partition_to_pinecone)

    spark.stop()
