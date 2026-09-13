# =========================
# WAFv2 for CloudFront
# Note: For scope = "CLOUDFRONT", resources must be created with a us-east-1 provider alias:
# provider "aws" { alias = "us_east_1" region = "us-east-1" }
# =========================

resource "aws_wafv2_web_acl" "this" {
  provider = aws
  name        = var.name
  description = "Baseline WAF for CloudFront using AWS Managed Rules"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  # 0) Common protections (SQLi/XSS, etc.)
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 10
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.spa_bucket}-waf-Common"
      sampled_requests_enabled   = true
    }
  }

  # 1) Known bad inputs
  rule {
    name     = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    priority = 20
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.spa_bucket}-waf-KnownBadInputs"
      sampled_requests_enabled   = true
    }
  }

  # 2) IP reputation
  rule {
    name     = "AWS-AWSManagedRulesAmazonIpReputationList"
    priority = 30
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.spa_bucket}-waf-IpReputation"
      sampled_requests_enabled   = true
    }
  }

  # 3) Anonymous IP (TOR/VPN/proxies) - optional (conditionally included)
  dynamic "rule" {
    for_each = var.waf_enable_anonymous_ip_rule ? [1] : []
    content {
      name     = "AWS-AWSManagedRulesAnonymousIpList"
      priority = 40
      override_action {
        count {}
      }
      statement {
        managed_rule_group_statement {
          name        = "AWSManagedRulesAnonymousIpList"
          vendor_name = "AWS"
        }
      }
      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.spa_bucket}-waf-AnonymousIp"
        sampled_requests_enabled   = true
      }
    }
  }

  # 4) Simple rate limit per IP
  rule {
    name     = "RateLimitPerIP"
    priority = 50
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit_requests_per_5min
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.spa_bucket}-waf-RateLimit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.spa_bucket}-waf-WebACL"
    sampled_requests_enabled   = true
  }

  tags = {
    ManagedBy = "OpenTofu"
    Purpose   = "cloudfront-waf"
  }
}

output "waf_arn" { value = aws_wafv2_web_acl.this.arn }