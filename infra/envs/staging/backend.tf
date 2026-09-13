terraform {
  backend "s3" {
    bucket = "visa-nav-tfstate-us-east-1"
    key = "staging/terraform.tfstate"
    region = "us-east-1"
    dynamodb_table = "visa-nav-tf-locks"
    encrypt = true
  }
}