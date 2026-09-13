resource "aws_sqs_queue" "dlq" {
  name = "${var.name}-dlq"
  message_retention_seconds = 1209600 # 14 days
}


resource "aws_sqs_queue" "main" {
  name = var.name
  visibility_timeout_seconds= var.visibility_timeout_seconds
  message_retention_seconds = var.message_retention_seconds
  receive_wait_time_seconds = var.receive_wait_time_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount = var.dlq_max_receive_count
  })
}