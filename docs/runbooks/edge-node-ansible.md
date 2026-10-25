# Runbook — configure the edge node with Ansible

`infra/ansible/site.yml` turns the fresh Ubuntu 24.04 EC2 instance created by Terraform into the `site-01` edge node: hardened base OS, `node_exporter`, single-node k3s that pulls from private ECR with the instance profile, and Argo CD pulling `sites/site-01` from the GitOps repo (PRD FR-PLT-2, ADR-002).

| Role | What it does |
| --- | --- |
| `common` | apt cache + upgrade, unattended-upgrades (no automatic reboot), SSH drop-in (no root login, no password / keyboard-interactive auth), ufw: deny incoming, SSH only from `ADMIN_CIDR`, allow the k3s pod/service CIDRs |
| `node_exporter` | pinned release (checksum-verified), systemd unit, `:9100` reachable only from the cluster network (ufw + Security Group) |
| `k3s` | pinned release binary + systemd unit, `disable: [traefik, servicelb]`, kubelet `ecr-credential-provider` + `CredentialProviderConfig` for `*.dkr.ecr.*.amazonaws.com` |
| `argocd` | Argo CD from the argo-helm chart via the k3s Helm controller, GitOps repo registered (public by default, SSH deploy key from Vault when private), root App of Apps for `sites/<site_name>` |

## Tooling (WSL / Linux)

```bash
uv venv --python 3.12 ~/.venvs/minieyes-ansible
uv pip install --python ~/.venvs/minieyes-ansible/bin/python \
  "ansible-core>=2.17,<2.19" ansible-lint molecule "molecule-plugins[docker]" docker requests
export PATH="$HOME/.venvs/minieyes-ansible/bin:$PATH"
cd infra/ansible
export ANSIBLE_CONFIG="$PWD/ansible.cfg"   # needed on /mnt/c: Ansible ignores a world-writable cwd's ansible.cfg
ansible-galaxy collection install -r requirements.yml
```

## Inventory from Terraform

The inventory (`inventory/hosts.yml`) has one host, `edge-01`, whose address is read from the environment, so no IP is committed:

```bash
export EDGE_HOST="$(terraform -chdir=../terraform/envs/lab output -raw edge_public_ip)"
export ADMIN_CIDR="<your-ip>/32"     # same value as Terraform var.admin_cidr
ssh-keyscan -H "$EDGE_HOST" >> ~/.ssh/known_hosts
```

Site settings live in `inventory/group_vars/edge/main.yml` (`site_name: site-01`, GitOps repo URLs, `gitops_repo_private`).

## Private GitOps repo (optional)

1. Create a read-only deploy key on `HuanNguyen09/minieyes-gitops`.
2. Store the private key in an encrypted vars file next to `main.yml`:

   ```bash
   ansible-vault create inventory/group_vars/edge/vault.yml
   # vault_gitops_deploy_key: |
   #   -----BEGIN OPENSSH PRIVATE KEY-----
   #   ...
   ```

3. Set `gitops_repo_private: true`. The role then uses the SSH URL and applies the repository Secret with `kubectl apply -f -` (`no_log`), so the key is never written to disk on the node.

Never commit the vault password file (`.vault-pass*` is git-ignored).

## Run

```bash
ansible-playbook site.yml                       # add --ask-vault-pass if vault.yml exists
ansible-playbook site.yml                       # second run must report changed=0
VERIFY_ECR_IMAGE=<acct>.dkr.ecr.<region>.amazonaws.com/minieyes/detector:<tag> \
  ansible-playbook verify.yml
```

`verify.yml` checks against the real node what a container cannot: ufw active with only SSH allowed from outside the cluster, k3s at the pinned version without Traefik/servicelb, kubelet wired to `ecr-credential-provider` and a pod pulling the private ECR image with `imagePullPolicy: Always` reaching `Running`, and the Argo CD root app `Healthy` on `sites/site-01`. Re-run it **12 h or more** after `site.yml` to prove pulls survive the ECR token lifetime.

## Tests

`make test-ansible` runs `ansible-lint` (production profile), `ansible-playbook --syntax-check`, and Molecule (Docker, systemd-enabled Ubuntu 24.04 image) for `common` (without ufw) and `node_exporter`, including the idempotence step.

## Pinned versions

| Component | Version | Where |
| --- | --- | --- |
| k3s | `v1.36.5+k3s1` (stable channel) | `roles/k3s/defaults/main.yml` |
| ecr-credential-provider | `v1.37.0` from `artifacts.k8s.io/binaries/cloud-provider-aws` | `roles/k3s/defaults/main.yml` |
| node_exporter | `1.12.1` | `roles/node_exporter/defaults/main.yml` |
| argo-cd Helm chart | `10.11.1` | `roles/argocd/defaults/main.yml` |

To bump a binary, change the version and the sha256 for each architecture from the release's checksum file.

## Troubleshooting

- **Locked out of SSH:** the ufw rule uses `ADMIN_CIDR`; if your IP changed, update the Security Group (Terraform) and re-run with the new `ADMIN_CIDR` through EC2 Instance Connect / SSM, or `ufw allow from <new>/32 to any port 22 proto tcp` on the console.
- **ImagePullBackOff on ECR images:** check the instance profile has `AmazonEC2ContainerRegistryReadOnly`, IMDSv2 is reachable from the host (`curl -s -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60'`), and `journalctl -u k3s | grep -i credential`.
- **Argo CD not installed:** `k3s kubectl -n kube-system get helmchart argocd` and the `helm-install-argocd` job logs.
