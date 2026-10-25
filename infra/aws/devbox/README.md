# Dev box: where the infrastructure work runs

The admin key is used **once**, from the laptop, to create lower-privileged identities. All
later work runs on an EC2 dev box with short-lived instance credentials.

| Identity | Lives on | Can do | Credential |
|---|---|---|---|
| your admin user | laptop profile `minieyes-admin` | run `bootstrap.sh` once | access key, **deleted afterwards** |
| `operator-minieyes` | laptop profile `minieyes-operator` | start/stop the dev box, open an SSM shell on it | access key (written by the script, never shown) |
| `DevBox-MiniEyes-Claude` | the dev box | Terraform, ECR, EKS within the guardrails ([../iam](../iam/README.md)) | instance role, no key |

Bedrock, SageMaker, Amazon Q and Marketplace are explicitly denied for both lower identities
and inside the boundary of every role Terraform creates.

## Steps

1. In **your own terminal** (keys never go into chat or files in the repo):
   `aws configure --profile minieyes-admin` (region `ap-southeast-1`).
2. `AWS_PROFILE=minieyes-admin bash infra/aws/devbox/bootstrap.sh`
3. Delete the admin access key: IAM → Users → *your user* → Security credentials → Deactivate → Delete.
4. Connect: EC2 console → `minieyes-devbox` → Connect → Session Manager, then
   `sudo -iu ubuntu`, `tail -f /var/log/minieyes-devbox.log` until it reports done
   (`/var/lib/minieyes-devbox-ready` exists), `gh auth login` (add the `workflow` scope),
   `cd ~/minieyes && claude`.
   With the [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
   installed: `aws ssm start-session --target <instance-id> --profile minieyes-operator`.

## Cost control

`t3.xlarge` costs about 0.21 USD/h in Singapore; the 100 GB gp3 disk about 9 USD/month even when
stopped. The box stops itself after 2 h with no login, SSM session, Claude Code or Terraform
process. Start it again with
`aws ec2 start-instances --instance-ids <id> --profile minieyes-operator`.
