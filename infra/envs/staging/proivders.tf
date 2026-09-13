terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.15"
    }
    awscc = {
      source = "hashicorp/awscc"
      version = "~> 1.0"
    }
  }
}

provider "aws" {
  region = var.region
  profile = var.profile
  alias = "use1"
  default_tags {
    tags = { Project = var.project, Env = var.env}
  }
}