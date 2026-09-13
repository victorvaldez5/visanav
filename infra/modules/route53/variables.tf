variable "domain_name" {
  description = "Root domain (hosted zone name), e.g., example.com"
  type        = string
}

variable "comment" {
  description = "Optional comment for the hosted zone"
  type        = string
  default     = null
}

variable "force_destroy" {
  description = "If true, allows destroying the zone even if it has records"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to the hosted zone"
  type        = map(string)
  default     = {}
}

variable "certificate_arn" {
  description = "The arn of the acm certificate"
  type = string
}

variable "hosts" {
  description = "A list of hostnames to associate the records with"
  type = list(string)
}
variable "target_domain_name" {
  description = "The original domain name of the resource"
  type = string
}

variable "target_zone_id" {
  description = "The original zone id of the resource"
  type = string
}

variable "acm_validation_map" {
  type = map(object({
    name  = string
    type  = string
    value = string
  }))
  default = {}
}