#!/usr/bin/env bash
# Render gitops/ into a working copy of the separate minieyes-gitops repository (#29).
#
#   AWS_ACCOUNT_ID=... BASE_DOMAIN=1-2-3-4.sslip.io ACME_EMAIL=you@example.com \
#   EDGE_EIP=198.51.100.7 ADMIN_CIDR=203.0.113.5/32 scripts/seed-gitops.sh ../minieyes-gitops
#
# Values come from `terraform output` after the first apply. Only the five placeholders below
# are substituted; everything else is copied verbatim. Review, commit and push yourself.
set -euo pipefail
target=${1:?usage: seed-gitops.sh <path-to-minieyes-gitops-checkout>}
cd "$(dirname "$0")/.."

vars=(AWS_ACCOUNT_ID BASE_DOMAIN ACME_EMAIL EDGE_EIP ADMIN_CIDR)
for v in "${vars[@]}"; do
  [ -n "${!v:-}" ] || { echo "missing $v" >&2; exit 1; }
done
case "$ADMIN_CIDR" in 0.0.0.0/0) echo "ADMIN_CIDR must not be 0.0.0.0/0" >&2; exit 1;; esac

mkdir -p "$target"
while IFS= read -r -d '' file; do
  rel=${file#gitops/}
  case "$rel" in
    ci/*) out="$target/.github/workflows/${rel#ci/}" ;;  # kept out of this repo's workflows
    *) out="$target/$rel" ;;
  esac
  mkdir -p "$(dirname "$out")"
  python3 - "$file" "$out" <<'PY'
import os, re, sys
src, dst = sys.argv[1:]
names = {"AWS_ACCOUNT_ID", "BASE_DOMAIN", "ACME_EMAIL", "EDGE_EIP", "ADMIN_CIDR"}
text = open(src, encoding="utf-8").read()
text = re.sub(r"\$\{(\w+)\}", lambda m: os.environ[m.group(1)] if m.group(1) in names else m.group(0), text)
open(dst, "w", encoding="utf-8", newline="\n").write(text)
PY
done < <(find gitops -type f -print0)
echo "seeded $target - review with git diff, then commit and push"
