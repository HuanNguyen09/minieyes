# Public-only VPC: an Internet Gateway and public subnets, no NAT Gateway (ADR-004).
# Instantiated twice (cloud and site) with no peering between them.

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = var.name }
}

# Take every rule away from the default security group so nothing lands in an open group by accident.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.name}-default-deny" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = { Name = var.name }
}

resource "aws_subnet" "public" {
  count = var.public_subnet_count

  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr_block, var.subnet_newbits, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.public_subnet_tags, {
    Name = "${var.name}-public-${data.aws_availability_zones.available.names[count.index]}"
  })

  lifecycle {
    precondition {
      condition     = var.public_subnet_count <= length(data.aws_availability_zones.available.names)
      error_message = "public_subnet_count is larger than the number of available AZs."
    }
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  # Inline routes make the table exclusive: a route added out of band (NAT, peering) shows up as drift.
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  count = var.public_subnet_count

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
