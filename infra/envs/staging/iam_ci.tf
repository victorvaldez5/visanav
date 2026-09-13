# Register GitHub Actions as an OIDC provider. The spa_cdn module's uploader
# role trusts it.
resource "aws_iam_openid_connect_provider" "github" {
  url                          = "https://token.actions.githubusercontent.com"
  client_id_list              = ["sts.amazonaws.com"]
  thumbprint_list             = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# envs/dev/iam_spa_ci.tf
variable "spa_ci_principal_arn" {
  type = string
  default = null
}


resource "aws_iam_policy" "spa_write" {
  count = var.spa_ci_principal_arn == null ? 0 : 1
  name = "${var.project}-${var.env}-spa-write"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect: "Allow",
      Action: ["s3:PutObject","s3:PutObjectAcl","s3:DeleteObject"],
      Resource: ["${module.spa_bucket.bucket_arn}/*"]
    }]
  })
}


resource "aws_iam_role_policy_attachment" "spa_ci_attach" {
  count = var.spa_ci_principal_arn == null ? 0 : 1
  role = var.spa_ci_principal_arn
  policy_arn= aws_iam_policy.spa_write[0].arn
}
