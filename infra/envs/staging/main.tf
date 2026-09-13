module "vpc" {
  source = "../../modules/vpc"
  name = "${var.project}-${var.env}"
  cidr_block = "10.20.0.0/16"
  az_count = 2
  single_nat = true
}

resource "aws_secretsmanager_secret" "api_keys" {
  name = "${var.project}-${var.env}/api-keys"
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    PINECONE_API_KEY = var.pinecone_api_key
    INDEX_HOST = var.pinecone_index_host
    OPEN_AI_API_KEY = var.openai_api_key
    DJANGO_SECRET_KEY = var.django_secret_key
  })
}

resource "aws_acm_certificate" "visanavapp" {
  domain_name       = "visanav.app"
  subject_alternative_names = ["www.visanav.app"] # add other hostnames if needed
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
  tags = {
    Name = "visanav.app"
  }
}


# Central logs bucket
module "logs" {
  source = "../../modules/s3"
  name = "${var.project}-${var.env}-logs"
  enable_acls = true
}

# App buckets
module "spa_bucket" {
  source = "../../modules/s3"
  name = "${var.project}-${var.env}-spa"
}

# User Data Bucket
module "uploads_bucket" {
  source = "../../modules/s3"
  name = "${var.project}-${var.env}-uploads"
  log_bucket_id = module.logs.bucket
  log_prefix = "uploads/"
}

module "scraped_data_bucket" {
  source = "../../modules/s3"
  name = "${var.project}-${var.env}-scraped"
}

# Celery Queues (broker = sqs)
module "celery_default_q"  {
  source = "../../modules/sqs"
  name = "${var.project}-${var.env}-celery-default"
}

# module "celery_high_q"  {
#   source = "../../modules/sqs"
#   name = "${var.project}-${var.env}-celery-high"
# }
#
# module "celery_low_q" {
#   source = "../../modules/sqs"
#   name = "${var.project}-${var.env}-celery-low"
# }

resource "aws_security_group" "services" {
  name = "${var.project}-${var.env}-services"
  vpc_id = module.vpc.vpc_id

  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

module "aurora" {
  source = "../../modules/aurora"
  name = "${var.project}-${var.env}-aurora"
  vpc_id = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
  db_name = "visanav"
  db_username = "visanav_main"
  min_capacity = "0.5"
  max_capacity = "2"
  allow_source_sg_ids = [aws_security_group.services.id]
}

module "redis" {
  source = "../../modules/redis"
  name = "${var.project}-${var.env}-redis"
  vpc_id = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
  allow_source_sg_ids = [aws_security_group.services.id]
}

module "waf" {
  source = "../../modules/waf"
  name = "${var.project}-${var.env}-waf"
  spa_bucket = module.spa_bucket.bucket
}

module "spa_cdn" {
  source = "../../modules/cloudfront"
  name = "${var.project}-${var.env}-spa"
  spa_bucket = module.spa_bucket.bucket
  spa_bucket_id = module.spa_bucket.bucket_id
  spa_bucket_arn = module.spa_bucket.bucket_arn
  spa_bucket_regional_domain_name = module.spa_bucket.bucket_regional_domain_name
  log_bucket_domain = module.logs.bucket_domain_name
  waf_arn = module.waf.waf_arn
  api_domain = var.api_domain_url
  aliases = ["visanav.app", "www.visanav.app"]
  acm_certificate_arn = aws_acm_certificate.visanavapp.arn
}


module "ecr_api" {
  source = "../../modules/ecr"
  name = "${var.project}-${var.env}-api"
}

module "api" {
  source = "../../modules/apprunner"
  name = "${var.project}-${var.env}-api"
  ecr_repo = module.ecr_api.repository_url
  image_tag = "latest"
  environment = var.env
  private_subnet_ids = module.vpc.private_subnet_ids
  services_sg_id = aws_security_group.services.id
  database_secret_arn = module.aurora.secret_arn
  api_keys_secret_arn = aws_secretsmanager_secret_version.api_keys.arn
  env = {
    POSTGRES_USER = module.aurora.db_user
    POSTGRES_DB = module.aurora.db_name
    POSTGRES_HOST = module.aurora.endpoint
    POSTGRES_PORT = module.aurora.db_port
    REDIS_URL = "rediss://${module.redis.primary_endpoint}:6379/0"
    DJANGO_SETTINGS_MODULE = "api_project.prod"
    AWS_REGION = var.region
    PINECONE_API_KEY = var.pinecone_api_key
    INDEX_HOST = var.pinecone_index_host
    OPEN_AI_API_KEY = var.openai_api_key
    DJANGO_SECRET_KEY = var.django_secret_key
    CELERY_BROKER_URL = "sqs://"
    CELERY_RESULT_BACKEND = "rediss://${module.redis.primary_endpoint}:6379/0"
    FRONTEND_URL = var.spa_domain_url
    ALLOWED_HOSTS = "${var.spa_domain_url},${var.api_domain_url},visanav.app,www.visanav.app"
    CSRF_TRUSTED_ORIGINS = "https://${var.spa_domain_url},https://${var.api_domain_url},https://www.visanav.app,https://visanav.app"
  }

}

module "ecr_workers" {
  source = "../../modules/ecr"
  name = "${var.project}-${var.env}-workers"
}

# ECS Celery workers
module "celery" {
  source = "../../modules/ecs_fargate"
  name = "${var.project}-${var.env}-celery"
  ecr_image = module.ecr_api.repository_url
  ecr_repo_arn = module.ecr_api.repository_arn
  region = var.region
  private_subnet_ids = module.vpc.private_subnet_ids
  services_sg_id = aws_security_group.services.id
  command = ["celery","-A","api_project.celery","worker","-l","INFO"]
  secret_arns = {
    POSTGRES_PASSWORD = module.aurora.secret_arn
    API_KEYS = aws_secretsmanager_secret_version.api_keys.arn
  }
  secret_envs = {
    POSTGRES_PASSWORD = module.aurora.secret_arn
  }
  env = {
    POSTGRES_USER = module.aurora.db_user
    POSTGRES_DB = module.aurora.db_name
    POSTGRES_HOST = module.aurora.endpoint
    POSTGRES_PORT = module.aurora.db_port
    REDIS_URL = "rediss://${module.redis.primary_endpoint}:6379/0"
    DJANGO_SETTINGS_MODULE = "api_project.prod"
    PINECONE_API_KEY = var.pinecone_api_key
    INDEX_HOST = var.pinecone_index_host
    OPEN_AI_API_KEY = var.openai_api_key
    DJANGO_SECRET_KEY = var.django_secret_key
    AWS_REGION = var.region
    CELERY_BROKER_URL = "sqs://"
    CELERY_RESULT_BACKEND = "rediss://${module.redis.primary_endpoint}:6379/0?ssl_cert_reqs=required"
    FRONTEND_URL = var.spa_domain_url
    ALLOWED_HOSTS = "${var.spa_domain_url},${var.api_domain_url},visanav.app,www.visanav.app"
    CSRF_TRUSTED_ORIGINS = "https://${var.spa_domain_url},https://${var.api_domain_url},https://www.visanav.app,https://visanav.app"
  }
}

module "ecr_scraper" {
  source = "../../modules/ecr"
  name = "${var.project}-${var.env}-scraper"
}

# ECS Scrapy service
module "scrapy" {
  source = "../../modules/ecs_fargate"
  name = "${var.project}-${var.env}-scrapy"
  ecr_image = module.ecr_scraper.repository_url
  ecr_repo_arn = module.ecr_scraper.repository_arn
  region = var.region
  private_subnet_ids = module.vpc.private_subnet_ids
  services_sg_id = aws_security_group.services.id
  secret_arns = {
    DATABASE_SECRET_ARN = module.aurora.secret_arn
  }
  command = ["scrapy","crawl","uscis_spider"]
}

locals {
  dvo_map = {
    for dvo in aws_acm_certificate.visanavapp.domain_validation_options :
    dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}
module "spa_r53" {
  source = "../../modules/route53"
  domain_name = "visanav.app"
  hosts = ["visanav.app", "www.visanav.app"]
  target_domain_name = module.spa_cdn.spa_cdn_url
  target_zone_id = module.spa_cdn.spa_cdn_hosted_zone_id
  certificate_arn = aws_acm_certificate.visanavapp.arn
  acm_validation_map = {
    "visanav.app" = local.dvo_map["visanav.app"]
    "www.visanav.app" = local.dvo_map["www.visanav.app"]
  }
}

output "vpc_id" {
  value = module.vpc.vpc_id
}
output "private_subnets" {
  value = module.vpc.private_subnet_ids
}
output "public_subnets" {
  value = module.vpc.public_subnet_ids
}
output "spa_bucket" {
  value = module.spa_bucket.bucket
}
output "uploads_bucket" {
  value = module.uploads_bucket.bucket
}
output "scraped_data_bucket" {
  value = module.scraped_data_bucket.bucket
}
output "celery_default_q" {
  value = module.celery_default_q.queue_url
}
# output "celery_high_q" {
#   value = module.celery_high_q.queue_url
# }
# output "celery_low_q" {
#   value = module.celery_low_q.queue_url
# }
output "services_sg_id" {
  value = aws_security_group.services.id
}
output "db_endpoint" {
  value = module.aurora.endpoint
}
output "db_secret_arn" {
  value = module.aurora.secret_arn
}
output "redis_primary" {
  value = module.redis.primary_endpoint
}