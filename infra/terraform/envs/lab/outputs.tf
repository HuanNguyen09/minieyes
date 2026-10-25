output "account_id" {
  description = "AWS account id (ECR registry host, GitOps seed)."
  value       = local.account_id
}

output "region" {
  description = "AWS region of the lab."
  value       = var.region
}

output "cluster_name" {
  description = "EKS cluster name (aws eks update-kubeconfig --name ...; envs/lab-platform reads it)."
  value       = module.eks.cluster_name
}

output "cluster_admin_arns" {
  description = "IAM principals with EKS cluster-admin access entries."
  value       = local.cluster_admin_arns
}

output "admin_cidrs" {
  description = "Admin CIDRs; GitOps uses them with the edge EIP for the NLB loadBalancerSourceRanges (#40)."
  value       = local.admin_cidrs
}

output "base_domain" {
  description = "Base domain for ingress hosts; empty means <nlb-ip>.sslip.io (#40)."
  value       = var.base_domain
}

output "edge_public_ip" {
  description = "Elastic IP of the edge site (Ansible, NLB allow-list in #40)."
  value       = module.edge.public_ip
}

output "edge_instance_id" {
  description = "Edge instance id."
  value       = module.edge.instance_id
}

output "ansible_inventory" {
  description = "One-line inventory entry for infra/ansible."
  value       = "edge ansible_host=${module.edge.public_ip} ansible_user=ubuntu"
}

output "ecr_repository_urls" {
  description = "Map of ECR repository name to URL."
  value       = module.ecr.repository_urls
}

output "github_push_role_arn" {
  description = "Role for GitHub Actions on main (push images to ECR)."
  value       = module.github_oidc.push_role_arn
}

output "github_plan_role_arn" {
  description = "Read-only role for terraform plan on pull requests (run plan with -lock=false)."
  value       = module.github_oidc.plan_role_arn
}
