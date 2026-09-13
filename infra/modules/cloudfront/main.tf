resource "aws_cloudfront_response_headers_policy" "html_no_cache" {
  name = "${var.spa_bucket}-html-no-cache"
  comment = "Set no-cache for HTML responses"

  custom_headers_config {
    items {
      header   = "Cache-Control"
      value    = "no-cache, no-store, must-revalidate"
      override = true
    }
    items {
      header   = "Pragma"
      value    = "no-cache"
      override = true
    }
    items {
      header   = "Expires"
      value    = "0"
      override = true
    }
  }
}

# Cache policy that disables CloudFront caching (let browser see new HTML immediately)
resource "aws_cloudfront_cache_policy" "html_disabled_cache" {
  name    = "${var.spa_bucket}-html-disabled-cache"
  comment = "Disable CloudFront caching for HTML"

  default_ttl = 0
  max_ttl     = 0
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "${var.spa_bucket}-oac"
  description                       = "OAC for S3 origin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Forward all viewer headers/cookies/query strings to the API origin (good default for dynamic APIs)
resource "aws_cloudfront_origin_request_policy" "api_all_forward" {
  count   = var.api_domain == null ? 0 : 1
  name    = "${var.name}-cf-origin-api-all-forward"
  comment = "Forward all headers, cookies, and query strings to API origin"

  headers_config {
    header_behavior = "whitelist"
    headers {
      items = [
        "Content-Type",
        "Accept",
        "Accept-Language",
        "Origin",
        "Referer",
        "User-Agent",
        "X-Requested-With",
      ]
    }
  }
  cookies_config {
    cookie_behavior = "all"
  }
  query_strings_config {
    query_string_behavior = "all"
  }
}

# CloudFront Distribution using the S3 origin with OAC
resource "aws_cloudfront_distribution" "cdn" {
  enabled             = true
  comment             = "Static site via CloudFront + OAC"
  price_class         = "PriceClass_100" # adjust as needed
  default_root_object = "index.html"
  web_acl_id = var.waf_arn

  # Prefer modern protocols
  http_version  = "http2and3"
  is_ipv6_enabled = true
  aliases = var.aliases


  origin {
    domain_name = var.spa_bucket_regional_domain_name
    origin_id   = "s3-${var.spa_bucket_id}"
    # Bind the OAC
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }
  origin {
    origin_id = "api-origin"
    domain_name = var.api_domain

    custom_header {
      name  = "X-Forwarded-For"
      value = var.api_domain
    }
    custom_header {
      name  = "X-Forwarded-Proto"
      value = "https"
    }
    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

# Conditionally add /api/* behavior to route to backend
  ordered_cache_behavior {
      path_pattern           = "api/*"
      target_origin_id       = "api-origin"
      viewer_protocol_policy = "redirect-to-https"

      # Typical API methods; cache only safe methods (and OPTIONS for preflight)
      allowed_methods = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods  = ["GET", "HEAD", "OPTIONS"]

      # Disable CloudFront caching for API, forward everything to origin
      cache_policy_id        = aws_cloudfront_cache_policy.html_disabled_cache.id
      # AllViewerExceptHostHeader
      origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"

      compress = true
  }
    # Serve HTML with no-cache
  ordered_cache_behavior {
    path_pattern           = "*.html"
    target_origin_id       = "s3-${var.spa_bucket_id}"
    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD"]
    cached_methods = ["GET", "HEAD"]

    cache_policy_id            = aws_cloudfront_cache_policy.html_disabled_cache.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.html_no_cache.id
    compress                   = true
  }
  # }
  ordered_cache_behavior {
    path_pattern           = "index.html"
    target_origin_id       = "s3-${var.spa_bucket_id}"
    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD"]
    cached_methods  = ["GET", "HEAD"]

    cache_policy_id            = aws_cloudfront_cache_policy.html_disabled_cache.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.html_no_cache.id
    compress = true
  }

  default_cache_behavior {
    target_origin_id       = "s3-${var.spa_bucket_id}"
    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD"]
    cached_methods  = ["GET", "HEAD"]

    # Use AWS managed "CachingOptimized" cache policy
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    response_headers_policy_id = "67f7725c-6f97-4210-82d7-5512b31e9d03"
    compress = true
  }

  logging_config {
    bucket = var.log_bucket_domain
    include_cookies = false
    prefix = "cloudfront/"
  }


  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 500
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn = var.acm_certificate_arn
    cloudfront_default_certificate = true
    ssl_support_method = "sni-only"
    minimum_protocol_version       = "TLSv1"
  }


  tags = {
    ManagedBy = "OpenTofu"
    Purpose   = "cloudfront"
  }
}


# Bucket policy to allow CloudFront (via OAC) to read
# Note: Ensure your CloudFront distribution is configured with an OAC.
# This policy secures access to only the specified distribution via AWS:SourceArn.
data "aws_iam_policy_document" "cf_origin_read_from_cloudfront" {
  statement {
    sid     = "AllowCloudFrontReadObjects"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    resources = ["${var.spa_bucket_arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.cdn.arn]
    }
  }

  statement {
    sid     = "AllowCloudFrontListBucket"
    effect  = "Allow"
    actions = ["s3:ListBucket"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    resources = [var.spa_bucket_arn]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.cdn.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "cf_origin" {
  bucket = var.spa_bucket_id
  policy = data.aws_iam_policy_document.cf_origin_read_from_cloudfront.json
}

# ----------------------------------------------------------------------------------------------------------------
# IAM: Uploader role and policy for deploying site assets to the origin bucket
# ----------------------------------------------------------------------------------------------------------------
data "aws_iam_policy_document" "cf_origin_uploader_trust" {
  statement {
    effect = "Allow"
    principals {
      type        = "Federated"
      identifiers = [var.github_actions_oidc]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Limit to your repo; optionally pin to a branch or env by extending the pattern
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:*"]
    }
  }
}


resource "aws_iam_role" "cf_origin_uploader" {
  name               = "${var.spa_bucket}-cf-origin-uploader"
  assume_role_policy = data.aws_iam_policy_document.cf_origin_uploader_trust.json

  tags = {
    Purpose   = "cf-origin-deploy"
    Terraform = "true"
    ManagedBy = "OpenTofu"
  }
}

data "aws_iam_policy_document" "cf_invalidation_policy_doc" {
  statement {
    sid     = "InvalidateCdn"
    effect  = "Allow"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
      "cloudfront:ListInvalidations"
    ]
    resources = [aws_cloudfront_distribution.cdn.arn]
  }
}

resource "aws_iam_policy" "cf_invalidation_policy" {
  name   = "${var.spa_bucket}-cloudfront-invalidation"
  policy = data.aws_iam_policy_document.cf_invalidation_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "cf_uploader_invalidation_attach" {
  role       = aws_iam_role.cf_origin_uploader.name
  policy_arn = aws_iam_policy.cf_invalidation_policy.arn
}

# Write permissions for uploads and housekeeping
data "aws_iam_policy_document" "cf_origin_write_policy_doc" {
  statement {
    sid    = "WriteObjects"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:PutObjectTagging",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload"
    ]
    resources = ["${var.spa_bucket_arn}/*"]
  }

  statement {
    sid    = "ListBucket"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads"
    ]
    resources = [var.spa_bucket_arn]
  }
}

resource "aws_iam_policy" "cf_origin_write_policy" {
  name   = "${var.spa_bucket}-cf-origin-write"
  policy = data.aws_iam_policy_document.cf_origin_write_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "cf_origin_writer_attach" {
  role       = aws_iam_role.cf_origin_uploader.name
  policy_arn = aws_iam_policy.cf_origin_write_policy.arn
}
