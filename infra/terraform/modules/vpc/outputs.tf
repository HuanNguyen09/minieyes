output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "cidr_block" {
  description = "IPv4 CIDR of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the public subnets, one per AZ."
  value       = aws_subnet.public[*].id
}

output "public_routes" {
  description = "Routes of the public route table; used by tests to prove there is no NAT or peering route."
  value       = aws_route_table.public.route
}
