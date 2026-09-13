output "spa_cdn_url" {
  value       = aws_cloudfront_distribution.cdn.domain_name                                          # The actual value to be outputted
  description = "the domain name of the cdn distribution" # Description of what this output represents
}

output "spa_cdn_hosted_zone_id" {
  value = aws_cloudfront_distribution.cdn.hosted_zone_id
  description = "The hosted zone id of the cdn"
}