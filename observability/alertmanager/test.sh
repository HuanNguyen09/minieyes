#!/usr/bin/env bash
# Offline checks for the Alertmanager config (PRD §8: amtool check-config,
# amtool config routes test). Needs amtool on PATH.
#   bash observability/alertmanager/test.sh
# Inhibition needs a running Alertmanager: observability/tests/test_alertmanager_live.py.
set -euo pipefail

cd "$(dirname "$0")"
CONFIG=alertmanager.yaml
failures=0

check() {
  local name=$1; shift
  if "$@" >/dev/null 2>&1; then
    echo "ok   - $name"
  else
    echo "FAIL - $name"
    "$@" || true
    failures=$((failures + 1))
  fi
}

# expect_route <receiver> <labels...>
# amtool does not print group_by; grouping is asserted in
# observability/tests/test_alertmanager.py (static and on a live Alertmanager).
expect_route() {
  local receiver=$1; shift
  check "$* -> $receiver" \
    amtool config routes test --config.file="$CONFIG" --verify.receivers="$receiver" "$@"
}

check "amtool check-config" amtool check-config "$CONFIG"

# Every MiniEyes alert reaches Telegram.
expect_route telegram severity=critical alertname=CameraDown site=site-01 camera=cam1
expect_route telegram severity=critical alertname=EdgeSiteSilent site=site-01
expect_route telegram severity=critical alertname=PodCrashLooping site=cloud
expect_route telegram severity=warning alertname=LowFPS site=site-01 camera=cam1
expect_route telegram severity=warning alertname=DiskWillFillIn24h site=site-02
# Unknown severities are not lost.
expect_route telegram alertname=SomethingNew site=site-01
# kube-prometheus-stack's heartbeat and info-level alerts never page.
expect_route null alertname=Watchdog severity=none
expect_route null alertname=InfoInhibitor severity=none
expect_route null alertname=KubeQuotaAlmostFull severity=info

# The bot token is read from a mounted Secret, never inlined.
check "no inline bot_token" bash -c "! grep -Eq '^[[:space:]]*bot_token:' $CONFIG"
check "bot_token_file used" grep -q 'bot_token_file: /etc/alertmanager/secrets/' "$CONFIG"

if ((failures > 0)); then
  echo "$failures check(s) failed"
  exit 1
fi
echo "all Alertmanager checks passed"
