# Terraform

| Directory | State | Creates |
|---|---|---|
| `bootstrap/` | local `terraform.tfstate` (keep it; gitignored) | State bucket `minieyes-tfstate-<account>`, budget alarms 30/60 USD |
| `envs/lab/` | S3 `lab/terraform.tfstate` | `minieyes-cloud` + `minieyes-site` VPCs (no NAT, no peering), EKS `minieyes-lab`, ECR repos, GitHub OIDC roles, edge EC2 |
| `envs/lab-platform/` | S3 `lab/platform.tfstate` | Argo CD (Helm) and the default `gp3` StorageClass on EKS |
| `modules/*` | — | `vpc`, `ecr`, `github-oidc`, `eks`, `edge-ec2`, `budgets` |

Rules the deployer policies enforce (`infra/aws/iam`): region `ap-southeast-1`; IAM roles named
`minieyes-*` with the `Boundary-MiniEyes-Workload` boundary; everything tagged `Project=minieyes`;
EC2 types `m6i.large` / `t3.micro|small|medium`. Design notes: [ADR-004](../../docs/adr/004-public-subnets-no-nat.md).

## Test (offline, no credentials)

```bash
make test-tf   # fmt -check, init -backend=false, validate, terraform test (mock providers), tflint, trivy config
```

## Apply order (owner only, from the dev box)

```bash
# 1. state bucket + budget alarms (once)
cd infra/terraform/bootstrap
terraform init
TF_VAR_budget_alert_email=you@example.com terraform apply
BUCKET=$(terraform output -raw state_bucket)

# 2. network, EKS, ECR, OIDC roles, edge
cd ../envs/lab
cat > terraform.tfvars <<EOF        # gitignored
admin_cidr          = "<dev box public IP>/32"
edge_ssh_public_key = "<contents of ~/.ssh/id_ed25519.pub>"
# extra_admin_cidrs = ["<laptop IP>/32"]
EOF
terraform init -backend-config=bucket=$BUCKET
terraform plan -out=lab.tfplan && terraform apply lab.tfplan   # ~15-20 min (EKS)

# 3. Argo CD + gp3 default StorageClass (needs the cluster; run from admin_cidr)
cd ../lab-platform
terraform init -backend-config=bucket=$BUCKET
terraform plan -out=platform.tfplan && terraform apply platform.tfplan

# 4. edge: terraform -chdir=../lab output -raw ansible_inventory  → infra/ansible
```

CI plans on pull requests assume `minieyes-github-plan`, which can read state but not write the
lock file: run `terraform plan -lock=false` there.

## Teardown order

1. In the GitOps repo, remove the Traefik `LoadBalancer` Service and all PVC-backed apps (or delete
   the Argo CD applications) so AWS deletes the NLB and EBS volumes. Leftover NLBs block VPC deletion.
2. `terraform -chdir=infra/terraform/envs/lab-platform destroy`
3. `terraform -chdir=infra/terraform/envs/lab destroy` (ECR repos are force-deleted with their images)
4. Keep `bootstrap/`: the budget alarms keep watching and the bucket has `prevent_destroy`.
   At the very end, remove `prevent_destroy`, empty the bucket (all versions) and destroy.
5. Check the console for leftovers: EC2 → Load Balancers, Volumes, Elastic IPs.
