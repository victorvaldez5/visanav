variable "name" {
  type = string
}
variable "ecr_image" {
  type = string
}
variable "region" {
  type = string
}
variable "ecr_repo_arn" {
  description = "The arn of the ecr repository"
  type = string
}
variable "cpu" {
  type = number
  default = 512
}
variable "memory" {
  type = number
  default = 1024
}
variable "desired_count" {
  type = number
  default = 1
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "services_sg_id" {
  type = string
}
variable "command" {
  type = list(string)
  default = []
}
variable "secret_arns" {
  type = map(string)
  default = {}
}
variable "secret_envs" {
  type = map(string)
  default = {}
}
variable "env" {
  type = map(string)
  default = {}
}