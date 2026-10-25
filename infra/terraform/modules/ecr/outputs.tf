output "repository_arns" {
  description = "Map of repository name to ARN."
  value       = { for k, r in aws_ecr_repository.this : k => r.arn }
}

output "repository_urls" {
  description = "Map of repository name to URL (registry/name) for docker push and Helm values."
  value       = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}
