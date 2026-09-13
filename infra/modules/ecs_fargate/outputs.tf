output "instance_public_ip" {
  value       = ""                                          # The actual value to be outputted
  description = "The public IP address of the EC2 instance" # Description of what this output represents
}
output "task_definition_arn" {
  value = aws_ecs_task_definition.this.arn
  description = "The task definition arn"
}
output "ecs_cluster_id" {
  value = aws_ecs_cluster.this.id
}
