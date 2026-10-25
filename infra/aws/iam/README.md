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
