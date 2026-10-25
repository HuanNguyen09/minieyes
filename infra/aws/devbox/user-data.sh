#!/usr/bin/env bash
# cloud-init for the MiniEyes dev box (Ubuntu 24.04). Installs the same pinned toolchain the
# laptop used, then clones the repo for the ubuntu user. Log: /var/log/minieyes-devbox.log
set -euxo pipefail
exec > >(tee -a /var/log/minieyes-devbox.log) 2>&1
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl git jq make unzip zip gnupg python3 python3-venv \
  docker.io docker-compose-v2 docker-buildx
usermod -aG docker ubuntu
systemctl enable --now docker

BIN=/usr/local/bin
fetch() { curl -fsSL --retry 5 -o "$1" "$2"; }
cd /tmp

# AWS CLI v2
fetch awscli.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip
unzip -q awscli.zip && ./aws/install && rm -rf aws awscli.zip

# GitHub CLI
fetch /usr/share/keyrings/githubcli.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" \
  > /etc/apt/sources.list.d/github-cli.list
apt-get update && apt-get install -y gh

# Kubernetes, Terraform and lint tooling (versions match the laptop and CI)
fetch tf.zip https://releases.hashicorp.com/terraform/1.10.5/terraform_1.10.5_linux_amd64.zip
unzip -o -q tf.zip terraform -d $BIN && rm tf.zip
fetch helm.tgz https://get.helm.sh/helm-v3.16.2-linux-amd64.tar.gz
tar xzf helm.tgz --strip-components=1 -C $BIN linux-amd64/helm && rm helm.tgz
fetch $BIN/kubectl https://dl.k8s.io/release/v1.33.4/bin/linux/amd64/kubectl
fetch $BIN/k3d https://github.com/k3d-io/k3d/releases/download/v5.7.4/k3d-linux-amd64
fetch kc.tgz https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-linux-amd64.tar.gz
tar xzf kc.tgz -C $BIN kubeconform && rm kc.tgz
fetch hu.tgz https://github.com/helm-unittest/helm-unittest/releases/download/v1.1.2/helm-unittest-linux-amd64-1.1.2.tgz
mkdir hu && tar xzf hu.tgz -C hu && install hu/untt $BIN/helm-unittest && rm -rf hu hu.tgz
fetch $BIN/hadolint https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64
fetch gl.tgz https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_x64.tar.gz
tar xzf gl.tgz -C $BIN gitleaks && rm gl.tgz
fetch prom.tgz https://github.com/prometheus/prometheus/releases/download/v2.55.1/prometheus-2.55.1.linux-amd64.tar.gz
tar xzf prom.tgz --strip-components=1 -C $BIN prometheus-2.55.1.linux-amd64/promtool && rm prom.tgz
fetch am.tgz https://github.com/prometheus/alertmanager/releases/download/v0.27.0/alertmanager-0.27.0.linux-amd64.tar.gz
tar xzf am.tgz --strip-components=1 -C $BIN alertmanager-0.27.0.linux-amd64/amtool && rm am.tgz
fetch tflint.zip https://github.com/terraform-linters/tflint/releases/download/v0.53.0/tflint_linux_amd64.zip
unzip -o -q tflint.zip -d $BIN && rm tflint.zip
curl -fsSL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b $BIN v0.56.2
chmod +x $BIN/*

# Per-user tools: uv and Claude Code (signs in with the user's own Claude account, not Bedrock)
su - ubuntu -c 'curl -LsSf https://astral.sh/uv/0.12.10/install.sh | sh'
su - ubuntu -c 'curl -fsSL https://claude.ai/install.sh | bash'
su - ubuntu -c 'git clone https://github.com/HuanNguyen09/minieyes.git ~/minieyes'

# A dev box idle overnight costs money: stop it after 2 h with no login, no SSM session and no
# running Claude Code / Terraform (work left running in tmux keeps it up)
cat > /usr/local/sbin/minieyes-idle-stop <<'IDLE'
#!/usr/bin/env bash
if who | grep -q . || pgrep -f ssm-session-worker >/dev/null \
   || pgrep -x claude >/dev/null || pgrep -x terraform >/dev/null; then
  date +%s > /run/minieyes-last-active; exit 0
fi
last=$(cat /run/minieyes-last-active 2>/dev/null || date +%s)
[ $(( $(date +%s) - last )) -gt 7200 ] && shutdown -h now "idle for 2 h"
IDLE
chmod +x /usr/local/sbin/minieyes-idle-stop
date +%s > /run/minieyes-last-active
echo '*/10 * * * * root /usr/local/sbin/minieyes-idle-stop' > /etc/cron.d/minieyes-idle-stop

touch /var/lib/minieyes-devbox-ready
