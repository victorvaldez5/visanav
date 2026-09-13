# envs/dev/scrapy_schedule.tf
resource "aws_cloudwatch_event_rule" "scrapy_nightly" {
  name                = "${var.project}-${var.env}-scrapy-nightly"
  schedule_expression = "cron(0 6 1 * ? *)" # 06:00 UTC 1st day of every month
}

resource "aws_cloudwatch_event_target" "scrapy_run" {
  rule = aws_cloudwatch_event_rule.scrapy_nightly.name
  target_id = "run-scrapy"
  arn = module.scrapy.ecs_cluster_id
  role_arn = aws_iam_role.events_to_ecs.arn
  ecs_target {
    task_definition_arn = module.scrapy.task_definition_arn
    launch_type = "FARGATE"
    network_configuration {
      subnets = module.vpc.private_subnet_ids
      security_groups = [aws_security_group.services.id]
      assign_public_ip = false
      }
    }
  }


resource "aws_iam_role" "events_to_ecs" {
  name = "${var.project}-${var.env}-events-ecs"
  assume_role_policy = jsonencode({
    Version: "2012-10-17",
    Statement: [{ Effect: "Allow", Principal: { Service: "events.amazonaws.com" }, Action: "sts:AssumeRole" }]
  })
}


resource "aws_iam_role_policy" "events_to_ecs" {
  name = "allow-run-task"
  role = aws_iam_role.events_to_ecs.id
  policy = jsonencode({
    Version: "2012-10-17",
    Statement: [{
      Effect: "Allow",
      Action: ["ecs:RunTask","iam:PassRole"],
      Resource: [module.scrapy.task_definition_arn],
      Condition: { StringEquals: { "iam:PassedToService": "ecs-tasks.amazonaws.com" } }
    }]
  })
}