mock_provider "aws" {}

override_data {
  target = data.aws_caller_identity.current
  values = {
    account_id = "123456789012"
  }
}

variables {
  budget_alert_email = "owner@example.com"
}

run "budget_alarms_exist_before_anything_else" {
  command = plan

  assert {
    condition     = toset(output.budget_names) == toset(["minieyes-monthly-30usd", "minieyes-monthly-60usd"])
    error_message = "Bootstrap must create the 30 and 60 USD budget alarms."
  }
}

run "bucket_is_versioned" {
  command = plan

  assert {
    condition     = aws_s3_bucket.state.bucket == "minieyes-tfstate-123456789012"
    error_message = "State bucket must be named minieyes-tfstate-<account id> (deployer policy scope)."
  }

  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "State bucket must have versioning enabled."
  }
}

run "bucket_is_encrypted" {
  command = plan

  assert {
    condition = one([
      for r in aws_s3_bucket_server_side_encryption_configuration.state.rule :
      one(r.apply_server_side_encryption_by_default).sse_algorithm
    ]) == "AES256"
    error_message = "State bucket must use default server-side encryption (SSE-S3)."
  }
}

run "public_access_is_blocked" {
  command = plan

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.state.block_public_acls,
      aws_s3_bucket_public_access_block.state.block_public_policy,
      aws_s3_bucket_public_access_block.state.ignore_public_acls,
      aws_s3_bucket_public_access_block.state.restrict_public_buckets,
    ])
    error_message = "All four public access block settings must be true."
  }
}

# prevent_destroy is a lifecycle meta-argument and cannot be read from a plan;
# it is documented in main.tf and infra/terraform/README.md. The test pins the
# observable parts of the protection instead.
run "bucket_is_protected_and_old_versions_expire" {
  command = plan

  assert {
    condition     = aws_s3_bucket.state.force_destroy == false
    error_message = "State bucket must not be force-destroyable."
  }

  assert {
    condition = anytrue([
      for r in aws_s3_bucket_lifecycle_configuration.state.rule :
      r.status == "Enabled" && length(r.noncurrent_version_expiration) == 1
    ])
    error_message = "A lifecycle rule must expire noncurrent state versions."
  }

  assert {
    condition = anytrue([
      for r in aws_s3_bucket_lifecycle_configuration.state.rule :
      r.status == "Enabled" && length(r.abort_incomplete_multipart_upload) == 1
    ])
    error_message = "A lifecycle rule must abort incomplete multipart uploads."
  }
}

run "bucket_denies_insecure_transport" {
  command = plan

  assert {
    condition = anytrue([
      for s in data.aws_iam_policy_document.state.statement :
      s.effect == "Deny" && anytrue([
        for c in s.condition : c.variable == "aws:SecureTransport" && contains(c.values, "false")
      ])
    ])
    error_message = "Bucket policy must deny requests that do not use TLS."
  }
}
