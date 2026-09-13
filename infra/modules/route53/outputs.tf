output "zone_id" {
  description = "Hosted zone ID"
  value       = aws_route53_zone.this.zone_id
}

output "name_servers" {
  description = "Authoritative NS to delegate at the registrar"
  value       = aws_route53_zone.this.name_servers
}

output "zone_name" {
  description = "Hosted zone name"
  value       = aws_route53_zone.this.name
}

output "zone_arn" {
  description = "Hosted zone ARN"
  value       = aws_route53_zone.this.arn
}