// IAM role for Glue to assume
resource "aws_iam_role" "glue_service_role" {
  name = "${var.bucket_prefix}-glue-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "glue.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

// Policy to let Glue read the dev & prod buckets
resource "aws_iam_policy" "glue_s3_read" {
  name        = "${var.bucket_prefix}-glue-s3-read"
  description = "Allow Glue to list and get objects from dev/prod buckets"
  policy      = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListBuckets"
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = [
          aws_s3_bucket.dev.arn,
        ]
      },
      {
        Sid    = "ReadObjects"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "${aws_s3_bucket.dev.arn}/*",
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_attach_s3" {
  role       = aws_iam_role.glue_service_role.name
  policy_arn = aws_iam_policy.glue_s3_read.arn
}

// (Optional) Attach the AWS managed Glue service policy for catalog access
resource "aws_iam_role_policy_attachment" "glue_service_managed" {
  role       = aws_iam_role.glue_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

// Glue Data Catalog database
resource "aws_glue_catalog_database" "uscis_db" {
  name = "${var.bucket_prefix}_catalog"
}

// Crawler that scans both dev & prod buckets
resource "aws_glue_crawler" "s3_crawler" {
  name         = "${var.bucket_prefix}-crawler"
  database_name = aws_glue_catalog_database.uscis_db.name
  role     = aws_iam_role.glue_service_role.arn
  # If you have a dedicated S3 location for crawler scripts, set python_script_location here

  s3_target {
    path = "s3://${aws_s3_bucket.dev.bucket}/"
  }

  # Optional: Only if you want incremental updates
  configuration = jsonencode({
    Version               = 1.0
    CrawlerOutput         = { Partitions = { AddOrUpdateBehavior = "InheritFromTable" } }
    Grouping              = { TableGroupingPolicy = "CombineCompatibleSchemas" }
  })

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  # You can schedule it instead of a one‐off run
  # schedule = "cron(0 12 * * ? *)"
}

resource "aws_glue_job" "clean_and_enrich_text" {
  name = "${var.bucket_prefix}-clean-and-enrich-text"
  role_arn = aws_iam_role.glue_service_role.arn

  execution_property {
    max_concurrent_runs = 1
  }

  command {
    name = "glueetl"
    python_version = "3"
    script_location = "s3://${local.dev_bucket_name}/glue-scripts/clean_and_extract_text.py"
  }

  default_arguments = {
    "--TempDir" = "s3://${local.dev_bucket_name}/glue-scripts/temp/"
    "--enable-metrics" = ""
    "--extra-py-files" = "s3://${aws_s3_bucket.dev.bucket}/glue-scripts/vendor.zip"
    "NLTK_DATA" = "/dependencies/nltk_data"
  }

  glue_version       = "5.0"
  number_of_workers  = 3
  worker_type        = "G.1X"
  max_retries        = 1
  timeout = 60
}
