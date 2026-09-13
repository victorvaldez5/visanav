data "aws_availability_zones" "this" { state = "available" }

locals {
  azs = slice(data.aws_availability_zones.this.names, 0, var.az_count)
  public_cidrs = [for i in range(var.az_count) : cidrsubnet(var.cidr_block, 8, i)]
  private_cidrs = [for i in range(var.az_count) : cidrsubnet(var.cidr_block, 8, i + 100)]
}
# Create VPC, 2 AZs
resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = {
    Name = "${var.name}-vpc"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.this.id
}

# Public subnets (NAT/egress), Private app subnets (for App Runner connectors/ECS), Isolated data subnets (RDS/Redis)
resource "aws_subnet" "public" {
  for_each = { for idx, az in local.azs : idx => az }
  vpc_id = aws_vpc.this.id
  availability_zone = each.value
  cidr_block = local.public_cidrs[tonumber(each.key)]
  map_public_ip_on_launch = true
  tags = {Name = "${var.name}-public-${each.value}"}
}

# Private Subnets
resource "aws_subnet" "private" {
  for_each = { for idx, az in local.azs : idx => az }
  vpc_id = aws_vpc.this.id
  availability_zone = each.value
  cidr_block = local.private_cidrs[tonumber(each.key)]
  tags = {Name = "${var.name}-private-${each.value}"}
}

# Network Access Tunnel (NAT)
resource "aws_eip" "nat" {
  count = var.single_nat ? 1 : var.az_count
  domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
  count = var.single_nat ? 1 : var.az_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id = values(aws_subnet.public)[var.single_nat ? 0 : count.index].id
  depends_on = [aws_internet_gateway.igw]
}

# Route tables - Public
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public
  subnet_id = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  for_each = aws_subnet.private
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    nat_gateway_id = var.single_nat ? aws_nat_gateway.nat[0].id : aws_nat_gateway.nat[tonumber(each.key)].id
  }
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private
  subnet_id = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}