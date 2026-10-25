# AWS access for MiniEyes

Claude Code runs on a dev-box EC2 whose instance role carries the deployer policies, so Terraform
uses short-lived instance credentials and **no access key exists anywhere**.

## Policies

| Policy | Kind | Purpose |
|---|---|---|
| `Deployer-MiniEyes-Infra` (`deployer-infra.json`) | allow | EC2/VPC, EKS clusters `minieyes-*`, ECR repos `minieyes*`, EKS log groups, KMS keys tagged `Project=minieyes`, the `minieyes-tfstate-*` bucket, SSM parameters `/minieyes/*`, Budgets. Load balancers and Auto Scaling are read-only. |
| `Deployer-MiniEyes-Iam` (`deployer-iam.json`) | allow | Roles, policies and instance profiles named `minieyes-*` and the GitHub OIDC provider. **A role can only be created or given permissions if it carries the workload boundary.** Roles can be passed only to EC2 and EKS. |
| `Deployer-MiniEyes-Guardrails` (`deployer-guardrails.json`) | deny | Explicit denies that win over any allow (see below). |
| `Boundary-MiniEyes-Workload` (`workload-boundary.json`) | permissions boundary | The ceiling for every `minieyes-*` role Terraform creates: what EKS, nodes, EBS CSI, the edge EC2 and the GitHub roles need, no IAM writes, no Bedrock. |
| `AmazonSSMManagedInstanceCore` | AWS managed | Session Manager access to the dev box, so it needs no inbound port. |

## Why the dev box cannot escalate

| Escalation path | Blocked by |
|---|---|
| Create a role with `*:*` and launch an EC2 with it | Every `minieyes-*` role must carry `Boundary-MiniEyes-Workload` (allow condition + explicit deny); effective permissions = policy ∩ boundary, and the boundary has no IAM writes. |
| Remove or swap the boundary | `iam:DeleteRolePermissionsBoundary` denied; `PutRolePermissionsBoundary` only to the same boundary. |
| Edit its own or the boundary's policies | They are named `Deployer-*` / `Boundary-*` and the role `DevBox-*`, outside `minieyes-*`; all other IAM writes are denied. |
| Create users, access keys or login profiles | Denied (not a `minieyes-*` role/policy/profile). |
| Assume another role | `sts:AssumeRole` denied outright. |
| Pass a privileged existing role to a new instance | `iam:PassRole` only on `minieyes-*` roles, only to EC2/EKS. |
| Hijack another instance (user data, instance profile, stop/start, snapshots, launch templates) | Denied unless the resource is tagged `Project=minieyes`, and existing resources cannot be re-tagged into the project. |
| Read other projects' secrets from SSM Parameter Store | Only `/minieyes/*` and public `/aws/service/*` are readable. |
| Take over another EKS cluster | EKS writes only on clusters named `minieyes-*`. |

**Bedrock / paid AI:** `bedrock:*`, `bedrock-agentcore:*`, `sagemaker:*`, `q:*`, `qbusiness:*`
and `aws-marketplace:*` (model subscriptions) are explicitly denied for the dev box and inside the
boundary, so no project role can call them either.

Cost guards: everything outside `ap-southeast-1` is denied (except global IAM/STS/Budgets), and
`RunInstances` only allows `m6i.large` and `t3.micro|small|medium`.

`test_policies.py` checks these invariants offline:
`uv run --no-project --with pytest pytest infra/aws/iam -q`.

### Residual risks (accepted for a lab; say so in reviews)
- `iam:UpdateAssumeRolePolicy` on `minieyes-*` roles could add an external trust; that principal
  would still be capped by the boundary. IAM Access Analyzer (external access) flags it.
- `ec2:*` can still change networking (security groups, routes) of non-project VPCs.
- Strongest isolation: a dedicated AWS account for MiniEyes, plus an SCP denying Bedrock if the
  account is in AWS Organizations.

## Setup (once)
1. AWS CloudShell in `ap-southeast-1`, as an admin (not root):
   `git clone https://github.com/HuanNguyen09/minieyes && bash minieyes/infra/aws/iam/create-devbox-role.sh`
2. Launch the dev box: Ubuntu 24.04, `t3.xlarge`, gp3 100 GB, IMDSv2 required,
   instance profile `DevBox-MiniEyes-Claude`, security group with **no inbound rules**.
   Do **not** tag it `Project=minieyes` — untagged, the role cannot stop, modify or re-role it.
3. Connect with Session Manager. Stop the instance when idle (~0.21 USD/h; the disk is billed while stopped).

## Terraform rule
Every IAM role Terraform creates must be named `minieyes-*` and set
`permissions_boundary = "arn:aws:iam::<account>:policy/Boundary-MiniEyes-Workload"`
(terraform-aws-modules: `iam_role_permissions_boundary`), and every resource must carry
`Project = "minieyes"` (provider `default_tags`). Otherwise the apply is denied.
