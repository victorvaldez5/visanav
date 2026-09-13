variable "name" {
  type = string
}
variable "vpc_id" {
  type = string
}
variable "subnet_ids" {
  type = list(string)
}
variable "engine_version" {
  type = string
  default = "7.1"
}
variable "node_type" {
  type = string
  default = "cache.t4g.micro"
}
variable "replicas_per_node" {
  type = number
  default = 1
} # 1 primary + replicas
variable "allow_source_sg_ids" {
  type = list(string)
  default = []
}