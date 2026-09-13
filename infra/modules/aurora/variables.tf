variable "name" {
  type = string
}
variable "db_name" {
  type = string
  default = "visanav"
}
variable "engine" {
  type = string
  default = "aurora-postgresql"
}
variable "engine_ver" {
  type = string
  default = "16.8"
}
variable "min_capacity"{
  type = number
  default = 0.5
} # ACUs
variable "max_capacity"{
  type = number
  default = 2
}
variable "subnet_ids" {
  type = list(string)
}
variable "vpc_id" {
  type = string
}
variable "db_username" {
  type = string
}
variable "backup_retention_period" {
  type = number
  default = 7
}
variable "allow_source_sg_ids" {
  type = list(string)
  default = []
}