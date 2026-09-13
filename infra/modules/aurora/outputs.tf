output "cluster_arn" {
  value = aws_rds_cluster.this.arn
}
output "endpoint" {
  value = aws_rds_cluster.this.endpoint
}
output "reader_endpoint"{
  value = aws_rds_cluster.this.reader_endpoint
}
output "db_sg_id" {
  value = aws_security_group.db.id
}
output "db_user" {
  value = aws_rds_cluster.this.master_username
}
output "db_name" {
  value = aws_rds_cluster.this.database_name
}
output "db_port" {
  value = aws_rds_cluster.this.port
}

output "secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}