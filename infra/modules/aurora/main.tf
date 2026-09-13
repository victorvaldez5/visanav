resource "aws_db_subnet_group" "this" {
  name = "${var.name}-db-subnets"
  subnet_ids = var.subnet_ids
}


resource "aws_security_group" "db" {
  name = "${var.name}-db-sg"
  description = "Aurora PGSQL access"
  vpc_id = var.vpc_id
}

resource "aws_security_group_rule" "ingress_pg" {
  for_each = toset(var.allow_source_sg_ids)
  type = "ingress"
  from_port = 5432
  to_port = 5432
  protocol = "tcp"
  security_group_id = aws_security_group.db.id
  source_security_group_id = each.value
}

resource "aws_security_group_rule" "egress_all" {
  type = "egress"
  from_port = 0
  to_port = 0
  protocol = "-1"
  security_group_id = aws_security_group.db.id
  cidr_blocks = ["0.0.0.0/0"]
}

# Generate & store a password in Secrets Manager
resource "random_password" "master" {
  length = 24
  special = true
}

resource "random_password" "admin" {
  length = 24
  special = true
}


resource "aws_secretsmanager_secret" "db" {
  name = "${var.name}/database-creds"
}


resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = random_password.master.result
}

resource "aws_secretsmanager_secret" "admin" {
  name = "${var.name}/superuser-creds"
}

resource "aws_secretsmanager_secret_version" "admin" {
  secret_id = aws_secretsmanager_secret.admin.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.master.result
  })
}

resource "aws_rds_cluster" "this" {
  cluster_identifier = var.name
  engine = var.engine
  engine_version = var.engine_ver
  database_name = var.db_name
  master_username = var.db_username
  master_password = random_password.master.result
  storage_encrypted = true
  deletion_protection = false
  apply_immediately = true
  copy_tags_to_snapshot = true
  backup_retention_period = var.backup_retention_period
  db_subnet_group_name = aws_db_subnet_group.this.name
  vpc_security_group_ids = concat([aws_security_group.db.id], var.allow_source_sg_ids)

  enable_http_endpoint = true

  serverlessv2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }
}

# Serverless v2 instances
resource "aws_rds_cluster_instance" "this" {
  count = 1
  identifier = "${var.name}-instance-${count.index}"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class = "db.serverless"
  engine = aws_rds_cluster.this.engine
  engine_version = aws_rds_cluster.this.engine_version
}

resource "aws_iam_role" "rds_data_api_role" {
  name = "${var.name}-rds-data-api-role"
  assume_role_policy = data.aws_iam_policy_document.rds_data_api_trust.json
}

resource "aws_rds_cluster_role_association" "data_api" {
  db_cluster_identifier = aws_rds_cluster.this.id
  feature_name = "s3Export"
  role_arn = aws_iam_role.rds_data_api_role.arn
}

data "aws_iam_policy_document" "rds_data_api_trust" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role_policy" "rds_data_api_inline" {
  name = "${var.name}-rds-data-api-policy"
  role = aws_iam_role.rds_data_api_role.id
  policy = data.aws_iam_policy_document.rds_data_api_permissions.json
}

data "aws_iam_policy_document" "rds_data_api_permissions" {
  statement {
    sid    = "AllowRDSDataAPI"
    effect = "Allow"
    actions = [
      "rds-data:BatchExecuteStatement",
      "rds-data:BeginTransaction",
      "rds-data:CommitTransaction",
      "rds-data:ExecuteStatement",
      "rds-data:RollbackTransaction",
      "rds-data:BatchExecuteSql" // ignored by PG but harmless
    ]
    resources = [aws_rds_cluster.this.arn]
  }

  // Optional: allow Secrets Manager to retrieve DB creds for Query Editor v2
  statement {
    sid     = "AllowReadDBSecret"
    effect  = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [aws_secretsmanager_secret.db.arn, aws_secretsmanager_secret.admin.arn]
  }
}