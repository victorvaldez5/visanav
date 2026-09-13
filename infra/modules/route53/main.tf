resource "aws_route53_zone" "this" {
  name          = var.domain_name
  comment       = var.comment
  force_destroy = var.force_destroy
  tags          = var.tags
}

resource "aws_route53_record" "acm_validation" {
  for_each = var.acm_validation_map

  zone_id = aws_route53_zone.this.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.value]
}

resource "aws_acm_certificate_validation" "visanavapp" {
  certificate_arn        = var.certificate_arn
  validation_record_fqdns = [for r in aws_route53_record.acm_validation : r.fqdn]
}

resource "aws_route53_record" "alias_a" {
  for_each = toset(var.hosts)

  zone_id = aws_route53_zone.this.zone_id
  name    = each.value
  type    = "A"

  alias {
    name                   = var.target_domain_name
    zone_id                = var.target_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "alias_aaaa" {
  for_each = toset(var.hosts)

  zone_id = aws_route53_zone.this.zone_id
  name    = each.value
  type    = "AAAA"

  alias {
    name                   = var.target_domain_name
    zone_id                = var.target_zone_id
    evaluate_target_health = false
  }
}
