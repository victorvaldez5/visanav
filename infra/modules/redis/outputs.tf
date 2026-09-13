output "primary_endpoint" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}
output "reader_endpoint" {
  value = aws_elasticache_replication_group.this.reader_endpoint_address
}
output "redis_sg_id" {
  value = aws_security_group.redis.id
}