output "queue_url" {
  value = aws_sqs_queue.main.id
}
output "queue_arn" {
  value = aws_sqs_queue.main.arn
}
output "dlq_url" {
  value = aws_sqs_queue.dlq.id
}
output "dlq_arn" {
  value = aws_sqs_queue.dlq.arn
}