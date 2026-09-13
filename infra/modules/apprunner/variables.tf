variable "name" {
  type = string
}
variable "environment" {
  type = string
  default = "staging"
}
variable "ecr_repo" {
  type = string
}
variable "image_tag" {
  type = string
  default = "latest"
}
variable "cpu" {
  type = number
  default = 1024
}
variable "memory" {
  type = number
  default = 2048
}
variable "port" {
  type = number
  default = 8000
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "services_sg_id" {
  type = string
}
variable "env" {
  type = map(string)
  default = {}
}

variable "database_secret_arn" {
  type = string
}
variable "api_keys_secret_arn" {
  type = string
}