output "account_id" {
  description = "AWS account id (ECR registry host, GitOps seed)."
  value       = local.account_id
}

output "region" {
  description = "AWS region of the lab."
  value       = var.region
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
