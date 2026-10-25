# Keyless CI: GitHub Actions exchanges its OIDC token for short-lived AWS credentials.
# The deployer may create only this OIDC provider (no EKS/IRSA provider; EKS uses Pod Identity).
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # thumbprint_list omitted: AWS validates GitHub's certificate against its own trusted CAs.
}

locals {
  oidc_host = "token.actions.githubusercontent.com"
}

# --- push role: main branch only, ECR push to the project repositories --------------------------

data "aws_iam_policy_document" "push_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "push" {
  name                 = "minieyes-github-push"
  description          = "GitHub Actions on ${var.github_repo} main: push images to ECR"
  assume_role_policy   = data.aws_iam_policy_document.push_trust.json
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600
}

data "aws_iam_policy_document" "push" {
  statement {
    sid       = "RegistryLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # GetAuthorizationToken has no resource-level scoping
  }

  statement {
    sid = "PushProjectImages"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeImages", # CI skips the push when the immutable SHA tag already exists
    ]
    resources = var.ecr_repository_arns
  }
}

resource "aws_iam_role_policy" "push" {
  name   = "ecr-push"
  role   = aws_iam_role.push.name
  policy = data.aws_iam_policy_document.push.json
}

# --- plan role: pull requests, read-only (terraform plan -lock=false) ----------------------------

data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["repo:${var.github_repo}:pull_request"]
    }
  }
}

resource "aws_iam_role" "plan" {
  name                 = "minieyes-github-plan"
  description          = "GitHub Actions pull requests on ${var.github_repo}: read-only terraform plan"
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600
}

data "aws_iam_policy_document" "plan" {
  statement {
    sid = "ReadInfrastructure"
    actions = [
      "ec2:Describe*",
      "eks:Describe*",
      "eks:List*",
      "ecr:Describe*",
      "ecr:GetLifecyclePolicy",
      "ecr:GetRepositoryPolicy",
      "ecr:ListTagsForResource",
      "iam:Get*",
      "iam:List*",
      "kms:Describe*",
      "kms:List*",
      "logs:Describe*",
      "logs:ListTagsForResource",
      "budgets:ViewBudget",
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = ["*"]
  }

  # Read state only; PR plans run with -lock=false, so no lock object is written.
  statement {
    sid     = "ReadTerraformState"
    actions = ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation", "s3:GetBucketVersioning"]
    resources = [
      "arn:aws:s3:::${var.state_bucket_name}",
      "arn:aws:s3:::${var.state_bucket_name}/*",
    ]
  }
}

resource "aws_iam_role_policy" "plan" {
  name   = "read-only-plan"
  role   = aws_iam_role.plan.name
  policy = data.aws_iam_policy_document.plan.json
}
