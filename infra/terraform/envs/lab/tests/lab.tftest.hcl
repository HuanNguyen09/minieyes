mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
    }
  }
}

# apply against the mock provider (nothing real is created) so route attributes are known.
run "cloud_and_site_vpcs_are_not_peered" {
  command = apply

  assert {
    condition = alltrue([
      for r in concat(tolist(module.cloud_vpc.public_routes), tolist(module.site_vpc.public_routes)) :
      r.cidr_block == "0.0.0.0/0" && coalesce(r.vpc_peering_connection_id, "none") == "none"
    ])
    error_message = "VPC route tables may only route 0.0.0.0/0 to the Internet Gateway; no peering routes."
  }

  assert {
    condition     = module.cloud_vpc.cidr_block != module.site_vpc.cidr_block
    error_message = "cloud-vpc and site-vpc must use different address ranges."
  }
}
