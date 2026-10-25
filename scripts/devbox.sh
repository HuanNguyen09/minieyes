#!/usr/bin/env bash
# Run a command on the dev box as the ubuntu user through SSM Run Command, wait, print its output
# and return its exit code. Uses the least-privileged operator profile; no inbound port, no SSH.
#
#   scripts/devbox.sh 'cd ~/minieyes && git pull && make test'
#   TIMEOUT=7200 scripts/devbox.sh 'cd ~/minieyes/infra/terraform/envs/lab && terraform plan'
set -euo pipefail
export MSYS_NO_PATHCONV=1 AWS_REGION=ap-southeast-1 AWS_PAGER=""
PROFILE=${DEVBOX_PROFILE:-minieyes-operator}
TIMEOUT=${TIMEOUT:-3600}
cmd=${1:?usage: devbox.sh '<command>'}

instance=$(aws ec2 describe-instances --profile "$PROFILE" \
  --filters Name=tag:minieyes:role,Values=devbox Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
[ "$instance" != "None" ] || { echo "dev box is not running (start it with the operator profile)" >&2; exit 2; }

# base64 keeps quotes, $ and newlines intact; the script runs in a login shell of ubuntu
payload=$(printf '%s\n' "$cmd" | base64 -w0)
params=$(python3 - "$payload" "$TIMEOUT" <<'PY'
import json, sys
payload, timeout = sys.argv[1], sys.argv[2]
print(json.dumps({
    # one file per run: bash reads a script while executing it, so a shared file would be
    # overwritten under a concurrent run
    "commands": ["f=$(mktemp /tmp/devbox-cmd.XXXXXX.sh)",
                 f"echo {payload} | base64 -d > $f",
                 "chmod 644 $f",
                 "sudo -iu ubuntu bash -eo pipefail $f; rc=$?; rm -f $f; exit $rc"],
    "executionTimeout": [timeout],
}))
PY
)
id=$(aws ssm send-command --profile "$PROFILE" --instance-ids "$instance" \
  --document-name AWS-RunShellScript --parameters "$params" \
  --timeout-seconds 60 --query Command.CommandId --output text)

while :; do
  status=$(aws ssm get-command-invocation --profile "$PROFILE" --command-id "$id" \
             --instance-id "$instance" --query Status --output text 2>/dev/null || echo Pending)
  case "$status" in Pending|InProgress|Delayed) sleep 3 ;; *) break ;; esac
done
aws ssm get-command-invocation --profile "$PROFILE" --command-id "$id" --instance-id "$instance" \
  --query '[StandardOutputContent,StandardErrorContent]' --output text
code=$(aws ssm get-command-invocation --profile "$PROFILE" --command-id "$id" \
         --instance-id "$instance" --query ResponseCode --output text)
[ "$status" = Success ] || echo "[devbox] $status (exit $code)" >&2
exit $(( code < 0 ? 1 : code ))
