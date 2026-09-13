variable "name" {
  type = string
}
variable "spa_bucket" {
  type = string
}

variable "waf_enable_anonymous_ip_rule" {
  type        = bool
  default     = true
  description = "Enable AWSManagedRulesAnonymousIpList rule group"
}

variable "waf_rate_limit_requests_per_5min" {
  type        = number
  default     = 2000
  description = "Rate-based rule limit (requests per 5 minutes) per IP"
}

