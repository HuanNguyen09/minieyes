# Deployer IAM user

Terraform runs as an IAM user `minieyes-deployer` with two customer-managed policies,
never as root and never with `AdministratorAccess`.

| Policy | What it allows |
|---|---|
| `deployer-infra.json` → `MiniEyesDeployerInfra` | EC2/VPC, EKS, ECR, ELB, Auto Scaling, CloudWatch Logs, KMS, the `minieyes-tfstate-*` bucket and Budgets. Everything except IAM/STS/Budgets is denied outside `ap-southeast-1`, and `RunInstances` is denied for any type other than `m6i.large` / `t3.micro|small|medium`. |
| `deployer-iam.json` → `MiniEyesDeployerIam` | Create and change only `minieyes-*` roles, policies and instance profiles, the GitHub and EKS OIDC providers, and the service-linked roles EKS needs. Attaching `AdministratorAccess`, `IAMFullAccess` or `PowerUserAccess` is denied. |

The deployer policies are deliberately **not** named `minieyes-*`, so the user cannot edit its own permissions.

Known gap (accepted for a lab account): a `minieyes-*` role could still be given broad inline
permissions. Production would add a permissions boundary on every role Terraform creates.

## Setup (once, as an admin in the console)
1. IAM → Policies → Create policy → JSON → paste each file → name as above.
2. IAM → Users → Create user `minieyes-deployer` (no console access) → attach both policies.
3. User → Security credentials → Create access key → "Command Line Interface".
4. In WSL: `aws configure --profile minieyes` (region `ap-southeast-1`, output `json`).
5. Check: `aws sts get-caller-identity --profile minieyes`.

Rotate the key when the project ends, or delete the user after `terraform destroy`.

## Dev box (preferred): an EC2 with an instance role, no access keys

Claude Code runs on an EC2 instance whose role carries the same two policies, so Terraform
uses short-lived instance credentials and no access key exists anywhere.

1. AWS CloudShell in `ap-southeast-1`:
   `git clone https://github.com/HuanNguyen09/minieyes && bash minieyes/infra/aws/iam/create-devbox-role.sh`
   (creates `MiniEyesDeployerInfra`, `MiniEyesDeployerIam`, role + instance profile
   `DevBox-MiniEyes-Claude` with `AmazonSSMManagedInstanceCore`).
2. Launch the instance: Ubuntu 24.04, `t3.xlarge` (4 vCPU / 16 GiB), gp3 **100 GB** (Docker
   images incl. Triton), IMDSv2 required, instance profile `DevBox-MiniEyes-Claude`,
   tag `minieyes:protect=true` (the role cannot stop, terminate or re-role a protected instance),
   security group with **no inbound rules** — connect with SSM Session Manager or EC2 Instance Connect.
3. Stop it when idle (~0.21 USD/h running in Singapore; the EBS volume is billed while stopped).
