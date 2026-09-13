resource "aws_ecr_repository" "this" {
  name = var.name
  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }
  image_tag_mutability = "MUTABLE"
  encryption_configuration {
    encryption_type = "AES256"
  }
}


resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy = <<POLICY
  {
    "rules": [
      {
        "rulePriority": 1,
        "description": "Expire untagged images after 30 days",
        "selection": { "tagStatus": "untagged", "countType": "sinceImagePushed", "countUnit": "days", "countNumber": 30 },
        "action": { "type": "expire" }
      }
    ]
  }
  POLICY
}