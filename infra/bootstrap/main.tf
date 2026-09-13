provider "aws" {
  region = var.region
}

variable "project" {
  type = string
  default = "visa-nav"
}
variable "region" {
  type = string
  default = "us-east-1"
}
locals {
  state_bucket = "${var.project}-tfstate-${var.region}"
  lock_table = "${var.project}-tf-locks"
}


resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "locks" {
  name = local.lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}

output "state_bucket" { value = aws_s3_bucket.state.bucket }
output "lock_table" { value = aws_dynamodb_table.locks.name }