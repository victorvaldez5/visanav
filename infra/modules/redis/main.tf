resource "aws_elasticache_subnet_group" "this" {
  name = "${var.name}-redis-subnets"
  subnet_ids = var.subnet_ids
}


resource "aws_security_group" "redis" {
  name = "${var.name}-redis-sg"
  description = "Redis access"
  vpc_id = var.vpc_id
}


resource "aws_security_group_rule" "ingress_redis" {
  for_each = toset(var.allow_source_sg_ids)
  type = "ingress"
  from_port = 6379
  to_port = 6379
  protocol = "tcp"
  security_group_id = aws_security_group.redis.id
  source_security_group_id = each.value
}


resource "aws_security_group_rule" "egress_all" {
  type = "egress"
  from_port = 0
  to_port = 0
  protocol = "-1"
  security_group_id = aws_security_group.redis.id
  cidr_blocks = ["0.0.0.0/0"]
}


resource "aws_elasticache_replication_group" "this" {
  replication_group_id = var.name
  description = "Redis for app cache/results"
  engine = "redis"
  engine_version = var.engine_version
  node_type = var.node_type
  parameter_group_name = "default.redis7"
  subnet_group_name = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]
  automatic_failover_enabled = true
  multi_az_enabled = true
  num_node_groups = 1
  replicas_per_node_group = var.replicas_per_node
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
}