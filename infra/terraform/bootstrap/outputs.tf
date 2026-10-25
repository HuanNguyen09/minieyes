output "state_bucket" {
  description = "Name of the Terraform state bucket; pass it to `terraform init -backend-config=bucket=...` in envs/*."
  value       = aws_s3_bucket.state.bucket
}

output "backend_init_command" {
  description = "Ready-to-run init command for envs/lab."
  value       = "terraform init -backend-config=bucket=${aws_s3_bucket.state.bucket}"
}
