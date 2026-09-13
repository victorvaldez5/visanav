variable "name" {
  type = string
}
variable "spa_bucket" {
  type = string
}
variable "spa_bucket_id" {
  type = string
}
variable "spa_bucket_regional_domain_name" {
  type = string
}
variable "spa_bucket_arn" {
  type = string
}
variable "log_bucket_domain" {
  type = string
  description = "The s3 bucket that will store the logs"
}
variable "waf_arn" {
  type = string
}
variable "api_domain" {
  description = "The API domain to direct api requests to"
  type = string
}

variable "aliases" {
  description = "Alternate domain names (CNAMEs) for the distribution"
  type = list(string)
  default = []
}

variable "acm_certificate_arn" {
  description = "ARN of ACM cert in region covering all aliases"
  type = string
  default = null
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default = "immigration-ai-bot"
}

variable "github_actions_oidc" {
  description = "The github actions oidc toke"
  type = string
  default = "arn:aws:iam::945472131701:oidc-provider/token.actions.githubusercontent.com"
}