resource "aws_s3_bucket" "this" {
  bucket = var.name
  force_destroy = var.force_destroy
}


resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    object_ownership = var.enable_acls ? "ObjectWriter" : "BucketOwnerEnforced"
  }
}


resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id
  block_public_acls = var.enable_acls ? false : true
  block_public_policy = true
  ignore_public_acls = var.enable_acls ? false : true
  restrict_public_buckets = true
}


resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = var.versioning ? "Enabled" : "Suspended"
  }
}


resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


resource "aws_s3_bucket_logging" "this" {
  count = var.log_bucket_id == null ? 0 : 1
  bucket = aws_s3_bucket.this.id
  target_bucket = var.log_bucket_id
  target_prefix = coalesce(var.log_prefix, "logs/")
}