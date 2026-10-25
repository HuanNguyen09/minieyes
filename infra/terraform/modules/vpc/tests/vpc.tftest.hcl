mock_provider "aws" {}

override_data {
  target = data.aws_availability_zones.available
  values = {
    names = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
  }
}

variables {
  name                = "minieyes-test"
  cidr_block          = "10.10.0.0/16"
  public_subnet_count = 2
}

run "public_subnets_span_distinct_azs" {
  command = plan

  assert {
    condition     = length(aws_subnet.public) == 2
    error_message = "Expected one public subnet per requested count."
  }

  assert {
    condition     = length(distinct([for s in aws_subnet.public : s.availability_zone])) == 2
    error_message = "Public subnets must be in distinct availability zones."
  }
}

run "subnet_cidrs_are_derived_and_disjoint" {
  command = plan

  variables {
    public_subnet_count = 3
  }

  assert {
    condition = [for s in aws_subnet.public : s.cidr_block] == [
      "10.10.0.0/20", "10.10.16.0/20", "10.10.32.0/20",
    ]
    error_message = "Subnet CIDRs must be cidrsubnet(cidr_block, 4, index)."
  }

  # Equal-size blocks from cidrsubnet with distinct indexes can only overlap if they are equal.
  assert {
    condition     = length(distinct([for s in aws_subnet.public : s.cidr_block])) == 3
    error_message = "Subnet CIDRs must not overlap."
  }
}

run "invalid_cidr_is_rejected" {
  command = plan

  variables {
    cidr_block = "10.10.0.300/16"
  }

  expect_failures = [var.cidr_block]
}

run "host_address_instead_of_network_is_rejected" {
  command = plan

  variables {
    cidr_block = "10.10.5.0/16"
  }

  expect_failures = [var.cidr_block]
}

run "name_outside_project_prefix_is_rejected" {
  command = plan

  variables {
    name = "other-vpc"
  }

  expect_failures = [var.name]
}

# apply against the mock provider (nothing real is created) so generated IDs are known.
run "internet_gateway_default_route_and_no_nat" {
  command = apply

  assert {
    condition     = aws_internet_gateway.this.vpc_id == aws_vpc.this.id
    error_message = "An Internet Gateway must be attached to the VPC."
  }

  assert {
    condition = length(output.public_routes) == 1 && alltrue([
      for r in output.public_routes :
      r.cidr_block == "0.0.0.0/0" && r.gateway_id == aws_internet_gateway.this.id && coalesce(r.nat_gateway_id, "none") == "none"
    ])
    error_message = "The only public route must be 0.0.0.0/0 via the Internet Gateway (no NAT Gateway)."
  }

  assert {
    condition     = length(aws_route_table_association.public) == length(aws_subnet.public)
    error_message = "Every public subnet must use the public route table."
  }

  assert {
    condition     = alltrue([for s in aws_subnet.public : s.map_public_ip_on_launch])
    error_message = "Public subnets must assign public IPs (nodes reach the internet without NAT)."
  }
}
