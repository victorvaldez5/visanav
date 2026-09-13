terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.99.1"
    }
  }
}
# modules/ecs-fargate/main.tf (replace aws_iam_role_policy.task_inline)
resource "aws_iam_policy" "read_secrets" {
  name = "${var.name}-read-secrets"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect: "Allow",
      Action: ["secretsmanager:GetSecretValue"],
      Resource: [for arn in values(var.secret_arns) : arn]
    }]
  })
}


resource "aws_iam_policy" "sqs_consume" {
  name = "${var.name}-sqs-consume"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect: "Allow",
      Action: ["sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes","sqs:ChangeMessageVisibility", "sqs:SendMessage"],
      Resource: ["*"] # optionally scope to your 3 Celery queues
    }]
  })
}


resource "aws_iam_role_policy_attachment" "task_attach_read_secrets" {
  role = aws_iam_role.task.name
  policy_arn = aws_iam_policy.read_secrets.arn
}


resource "aws_iam_role_policy_attachment" "task_attach_sqs" {
  role = aws_iam_role.task.name
  policy_arn = aws_iam_policy.sqs_consume.arn
}

resource "aws_ecs_cluster" "this" {
  name = var.name
}

resource "aws_ecs_task_definition" "this" {
  family = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode = "awsvpc"
  cpu = tostring(var.cpu)
  memory = tostring(var.memory)
  execution_role_arn = aws_iam_role.exec.arn
  task_role_arn = aws_iam_role.task.arn
  container_definitions = jsonencode([
    {
      name = var.name
      image = var.ecr_image
      essential = true
      command = (length(var.command) > 0 ? var.command : null)
      environment = [for k, v in var.env : { name = k, value = v }]
      secrets = [for k, v in var.secret_envs : { name = k, valueFrom = v }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = var.region
          awslogs-stream-prefix = var.name
          awslogs-create-group  = "true"
        }
      }
    }
  ])
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}"
  retention_in_days = 30
}

resource "aws_ecs_service" "this" {
  name = var.name
  cluster = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count = var.desired_count
  launch_type = "FARGATE"
  network_configuration {
    subnets = var.private_subnet_ids
    security_groups = [var.services_sg_id]
    assign_public_ip = false
  }
}

resource "aws_iam_role" "exec" {
  name = "${var.name}-exec"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}


resource "aws_iam_role" "task" {
  name = "${var.name}-task"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

resource "aws_iam_policy" "ecr_pull" {
  name = "${var.name}-ecr-pull"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Sid: "AuthToken",
      Effect: "Allow",
      Action: ["ecr:GetAuthorizationToken"],
      Resource: "*"
    },
    {
      Sid: "PullFromRepo",
      Effect: "Allow",
      Action: ["ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer","ecr:BatchGetImage"],
      Resource: var.ecr_repo_arn
    }]
  })
}
resource "aws_iam_policy" "read_logs" {
  name = "${var.name}-read-logs"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Sid: "ReadWriteLogs",
      Effect: "Allow",
      Action: ["logs:*"],
      Resource: "*"
    }]
  })
}


data "aws_iam_policy_document" "sqs_access" {
  statement {
    effect = "Allow"
    actions = [
      "sqs:*"
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "s3_access" {
  statement {
    effect = "Allow"
    actions = [
      "s3:*"
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "rds_access" {
  statement {
    effect = "Allow"
    actions = [
      "rds:*"
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "exec_access_combined" {
  override_policy_documents = [
    data.aws_iam_policy_document.rds_access.json,
    data.aws_iam_policy_document.s3_access.json,
    data.aws_iam_policy_document.sqs_access.json,
  ]
}
resource "aws_iam_policy" "ecs_exec_access_policy" {
  name = "${var.name}-ecs-exec-access-policy"
  policy = data.aws_iam_policy_document.exec_access_combined.json
}

resource "aws_iam_role_policy_attachment" "exec_read_secrets" {
  role = aws_iam_role.exec.name
  policy_arn = aws_iam_policy.read_secrets.arn
}

resource "aws_iam_role_policy_attachment" "exec_attach_ecr" {
  role       = aws_iam_role.exec.name
  policy_arn = aws_iam_policy.ecr_pull.arn
}

resource "aws_iam_role_policy_attachment" "exec_read_write_logs" {
  policy_arn = aws_iam_policy.read_logs.arn
  role       = aws_iam_role.exec.name
}

resource "aws_iam_role_policy_attachment" "exec_services_access_combined" {
  policy_arn = aws_iam_policy.ecs_exec_access_policy.arn
  role = aws_iam_role.exec.name
}

resource "aws_iam_role_policy_attachment" "task_services_access_combined" {
  policy_arn = aws_iam_policy.ecs_exec_access_policy.arn
  role = aws_iam_role.task.name
}


data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}