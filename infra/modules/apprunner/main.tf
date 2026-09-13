
data "aws_iam_policy_document" "apprunner_access_trust" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"] # access (image pull) plane
    }
  }
}

data "aws_iam_policy_document" "apprunner_task_trust" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}


data "aws_caller_identity" "me" {}
data "aws_region" "current" {}
# Identity permissions for pulling from your private ECR repo
data "aws_iam_policy_document" "apprunner_ecr_pull" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # required by AWS
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:ListImages",
    ]
    resources = ["*"]
  }
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

data "aws_iam_policy_document" "secrets_access" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue"
    ]
    resources = [
      var.database_secret_arn,
      var.api_keys_secret_arn,
    ]
  }
  statement {
    actions   = ["ssm:GetParameter","ssm:GetParameters"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "task_access_combined" {
  override_policy_documents = [
    data.aws_iam_policy_document.secrets_access.json,
    data.aws_iam_policy_document.rds_access.json,
    data.aws_iam_policy_document.s3_access.json,
    data.aws_iam_policy_document.sqs_access.json,
  ]
}
resource "aws_iam_role" "apprunner_ecr_access" {
  name               = "${var.name}-apprunner-ecr-access"
  assume_role_policy = data.aws_iam_policy_document.apprunner_access_trust.json
}

resource "aws_iam_role" "apprunner_task_access" {
  name = "${var.name}-apprunner-task-access-role"
  assume_role_policy = data.aws_iam_policy_document.apprunner_task_trust.json
}

resource "aws_iam_policy" "apprunner_ecr_pull" {
  name   = "${var.name}-apprunner-ecr-pull"
  policy = data.aws_iam_policy_document.apprunner_ecr_pull.json
}

resource "aws_iam_policy" "apprunner_task_access_policy" {
  name = "${var.name}-apprunner-task-access-policy"
  policy = data.aws_iam_policy_document.task_access_combined.json
}
# Read only the DB secret
resource "aws_iam_role_policy" "apprunner_secrets_read" {
  name = "read-db-secret"
  role = aws_iam_role.apprunner_ecr_access.id
  policy = data.aws_iam_policy_document.secrets_access.json
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_pull_attach" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = aws_iam_policy.apprunner_ecr_pull.arn
}

resource "aws_iam_role_policy_attachment" "apprunner_task_access_trust" {
  role = aws_iam_role.apprunner_task_access.name
  policy_arn = aws_iam_policy.apprunner_task_access_policy.arn
}

resource "aws_apprunner_vpc_connector" "this" {
  vpc_connector_name = "${var.name}-vpc"
  subnets = var.private_subnet_ids
  security_groups = [var.services_sg_id]
}


resource "aws_apprunner_service" "this" {
  service_name = var.name
  source_configuration {
    image_repository {
      image_repository_type = "ECR"
      image_identifier = "${var.ecr_repo}:${var.image_tag}"

      image_configuration {
        port = tostring(var.port)
        runtime_environment_variables = var.env
        runtime_environment_secrets = {
          POSTGRES_PASSWORD = var.database_secret_arn
          API_KEYS = var.api_keys_secret_arn
        }
      }
    }

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }
    auto_deployments_enabled = true
  }


  instance_configuration {
    cpu = tostring(var.cpu)
    memory = tostring(var.memory)
    instance_role_arn = aws_iam_role.apprunner_task_access.arn
  }


  network_configuration {
    egress_configuration {
      egress_type = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.this.arn
    }
    ingress_configuration {
      is_publicly_accessible = true
    }
  }
  tags = {
    awsApplication = "VisaNav"
    environment = "${var.environment}"
  }
}


output "service_url" { value = aws_apprunner_service.this.service_url }