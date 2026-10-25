output "push_role_arn" {
  description = "Role for GitHub Actions on main (aws-actions/configure-aws-credentials role-to-assume)."
  value       = aws_iam_role.push.arn
}

output "plan_role_arn" {
  description = "Read-only role for terraform plan on pull requests."
  value       = aws_iam_role.plan.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider."
  value       = local.provider_arn
}
