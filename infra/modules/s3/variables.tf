variable "name" {
  type = string
}
variable "force_destroy" {
  type = bool
  default = false
}
variable "versioning" {
  type = bool
  default = true
}
variable "enable_acls" {
  description = "Enable S3 Acls on this bucket (needed for logs)"
  type = bool
  default = false
}
variable "log_bucket_id" {
  type = string
  default = null
}
variable "log_prefix" {
  type = string
  default = null
}