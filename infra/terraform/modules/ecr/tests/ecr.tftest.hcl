mock_provider "aws" {}

variables {
  repositories = ["minieyes/detector", "minieyes/event-api", "minieyes/camera-sim", "minieyes/model-yolov8n"]
}

run "one_scanned_immutable_repo_per_service" {
  command = plan

  assert {
    condition     = toset(keys(aws_ecr_repository.this)) == toset(var.repositories)
    error_message = "Expected exactly one ECR repository per service."
  }

  assert {
    condition     = alltrue([for r in aws_ecr_repository.this : r.image_tag_mutability == "IMMUTABLE"])
    error_message = "Image tags must be immutable (tag = git SHA)."
  }

  assert {
    condition     = alltrue([for r in aws_ecr_repository.this : r.image_scanning_configuration[0].scan_on_push])
    error_message = "Every repository must scan images on push."
  }
}

run "lifecycle_keeps_last_20_images" {
  command = plan

  assert {
    condition     = toset(keys(aws_ecr_lifecycle_policy.this)) == toset(var.repositories)
    error_message = "Every repository needs a lifecycle policy."
  }

  assert {
    condition = alltrue([
      for p in aws_ecr_lifecycle_policy.this : anytrue([
        for r in jsondecode(p.policy).rules :
        r.selection.tagStatus == "any" &&
        r.selection.countType == "imageCountMoreThan" &&
        r.selection.countNumber == 20 &&
        r.action.type == "expire"
      ])
    ])
    error_message = "Lifecycle policy must expire everything beyond the newest 20 images."
  }
}

run "repository_names_must_use_project_prefix" {
  command = plan

  variables {
    repositories = ["detector"]
  }

  expect_failures = [var.repositories]
}
