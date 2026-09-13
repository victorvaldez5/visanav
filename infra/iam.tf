# -------------------------------------------------------------------
# S3 IAM Roles
#    a) Task execution role (to pull image, send logs)
#    b) Task role         (to access S3)
#    c) EventBridge role  (to trigger RunTask)
# -------------------------------------------------------------------
resource "aws_iam_policy" "project_raul_s3_policy" {
  name        = "${var.bucket_prefix}-s3-access"
  description = "Least-privilege S3 access for the Project Raul app"
  policy      = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Sid    = "ListBuckets"
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = [
          aws_s3_bucket.dev.arn,
        ]
      },
      {
        Sid    = "ObjectActions"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.dev.arn}/*",
        ]
      }
    ]
  })
}

resource "aws_iam_role" "project_raul_app" {
  name = "project-raul-app-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "app_s3_access" {
  role       = aws_iam_role.project_raul_app.name
  policy_arn = aws_iam_policy.project_raul_s3_policy.arn
}

# -------------------------------------------------------------------
# ECR and ECS Fargate IAM Roles
#    a) Task execution role (to pull image, send logs)
#    b) Task role         (to access S3)
#    c) EventBridge role  (to trigger RunTask)
# -------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.bucket_prefix}-ecs-exec-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_exec_attach" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Re-use your S3 policy for the task itself
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.bucket_prefix}-ecs-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_s3_attach" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.project_raul_s3_policy.arn
}

# Role for EventBridge to invoke ECS
resource "aws_iam_role" "events_to_ecs" {
  name = "${var.bucket_prefix}-events-to-ecs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "events_to_ecs_policy" {
  name = "${var.bucket_prefix}-events-to-ecs-policy"
  role = aws_iam_role.events_to_ecs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ecs:RunTask",
          "iam:PassRole"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# -------------------------------------------------------------------
# AWS Bedrock Iam Policies
# -------------------------------------------------------------------

resource "aws_iam_role" "glue_bedrock" {
  name = "${var.project_prefix}-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "glue.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "glue_bedrock_policy" {
  role = aws_iam_role.glue_bedrock.name

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:*"
        ],
        Resource = "*"
      }
    ]
  })
}

# Register GitHub Actions as an OIDC provider
resource "aws_iam_openid_connect_provider" "github" {
  url                          = "https://token.actions.githubusercontent.com"
  client_id_list              = ["sts.amazonaws.com"]
  thumbprint_list             = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com"
}
