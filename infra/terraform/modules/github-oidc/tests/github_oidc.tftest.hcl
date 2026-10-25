mock_provider "aws" {
  # Policy documents feed role/policy arguments; give the mock valid JSON.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

variables {
  github_repo              = "HuanNguyen09/minieyes"
  permissions_boundary_arn = "arn:aws:iam::123456789012:policy/Boundary-MiniEyes-Workload"
  state_bucket_name        = "minieyes-tfstate-123456789012"
  ecr_repository_arns = [
    "arn:aws:ecr:ap-southeast-1:123456789012:repository/minieyes-detector",
    "arn:aws:ecr:ap-southeast-1:123456789012:repository/minieyes-event-api",
  ]
}

run "every_role_is_named_minieyes_and_carries_the_boundary" {
  command = plan

  assert {
    condition = alltrue([
      for r in [aws_iam_role.push, aws_iam_role.plan] :
      startswith(r.name, "minieyes-") && r.permissions_boundary == var.permissions_boundary_arn
    ])
    error_message = "Every IAM role must be named minieyes-* and carry Boundary-MiniEyes-Workload."
  }
}

run "github_oidc_provider_exists" {
  command = plan

  assert {
    condition     = aws_iam_openid_connect_provider.github.url == "https://token.actions.githubusercontent.com"
    error_message = "OIDC provider must be token.actions.githubusercontent.com."
  }

  assert {
    condition     = toset(aws_iam_openid_connect_provider.github.client_id_list) == toset(["sts.amazonaws.com"])
    error_message = "OIDC provider audience must be sts.amazonaws.com."
  }
}

run "push_role_trusts_only_main_branch" {
  command = plan

  assert {
    condition     = aws_iam_role.push.name == "minieyes-github-push"
    error_message = "Push role must be named minieyes-github-push."
  }

  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.push_trust.statement :
      toset(s.actions) == toset(["sts:AssumeRoleWithWebIdentity"]) && anytrue([
        for c in s.condition :
        c.test == "StringEquals" && c.variable == "token.actions.githubusercontent.com:aud" && toset(c.values) == toset(["sts.amazonaws.com"])
      ])
    ])
    error_message = "Push role trust must require aud = sts.amazonaws.com."
  }

  # StringEquals, not StringLike: no wildcard can widen the subject.
  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.push_trust.statement : anytrue([
        for c in s.condition :
        c.test == "StringEquals" && c.variable == "token.actions.githubusercontent.com:sub" &&
        toset(c.values) == toset(["repo:HuanNguyen09/minieyes:ref:refs/heads/main"])
      ])
    ])
    error_message = "Push role trust must require sub = repo:HuanNguyen09/minieyes:ref:refs/heads/main exactly."
  }
}

run "push_role_can_push_only_to_project_repos" {
  command = plan

  # The only statement on "*" is the registry login.
  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.push.statement :
      toset(s.actions) == toset(["ecr:GetAuthorizationToken"]) if contains(s.resources, "*")
    ])
    error_message = "Only ecr:GetAuthorizationToken may be granted on \"*\"."
  }

  assert {
    condition = anytrue([
      for s in data.aws_iam_policy_document.push.statement :
      contains(s.actions, "ecr:GetAuthorizationToken") && toset(s.resources) == toset(["*"])
    ])
    error_message = "Push role needs ecr:GetAuthorizationToken for docker login."
  }

  # Every other statement is scoped to exactly the project repositories, with explicit ECR actions.
  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.push.statement :
      toset(s.resources) == toset(var.ecr_repository_arns) &&
      alltrue([for a in s.actions : startswith(a, "ecr:") && !strcontains(a, "*") && !startswith(a, "ecr:Delete")])
      if !contains(s.resources, "*")
    ])
    error_message = "Push statements must target only the project repositories with explicit, non-destructive ECR actions."
  }

  assert {
    condition = anytrue([
      for s in data.aws_iam_policy_document.push.statement :
      contains(s.actions, "ecr:PutImage") && contains(s.actions, "ecr:CompleteLayerUpload")
    ])
    error_message = "Push role must be able to push images."
  }

  assert {
    condition     = aws_iam_role_policy.push.role == aws_iam_role.push.name
    error_message = "The push policy must be attached to the push role."
  }
}

run "plan_role_trusts_pull_requests_and_is_read_only" {
  command = plan

  assert {
    condition     = aws_iam_role.plan.name == "minieyes-github-plan"
    error_message = "Plan role must be named minieyes-github-plan."
  }

  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.plan_trust.statement :
      anytrue([
        for c in s.condition :
        c.test == "StringEquals" && c.variable == "token.actions.githubusercontent.com:sub" &&
        toset(c.values) == toset(["repo:HuanNguyen09/minieyes:pull_request"])
      ]) &&
      anytrue([
        for c in s.condition :
        c.test == "StringEquals" && c.variable == "token.actions.githubusercontent.com:aud" &&
        toset(c.values) == toset(["sts.amazonaws.com"])
      ])
    ])
    error_message = "Plan role trust must require sub = repo:HuanNguyen09/minieyes:pull_request and aud = sts.amazonaws.com."
  }

  # Read-only: every action is a Describe/Get/List/View call (no wildcards that include writes).
  assert {
    condition = alltrue(flatten([
      for s in data.aws_iam_policy_document.plan.statement : [
        for a in s.actions : can(regex("^[a-z0-9-]+:(Describe|Get|List|View|BatchGet)[A-Za-z]*\\*?$", a))
      ]
    ]))
    error_message = "Plan role may only hold Describe/Get/List/View actions."
  }

  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.plan.statement :
      toset(s.resources) == toset([
        "arn:aws:s3:::minieyes-tfstate-123456789012",
        "arn:aws:s3:::minieyes-tfstate-123456789012/*",
      ])
      if anytrue([for a in s.actions : startswith(a, "s3:")])
    ])
    error_message = "S3 access of the plan role must be limited to the state bucket."
  }

  assert {
    condition     = aws_iam_role_policy.plan.role == aws_iam_role.plan.name
    error_message = "The read-only policy must be attached to the plan role."
  }
}
