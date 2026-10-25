"""Every pod the charts render must pass the Kubernetes Pod Security "restricted" profile,
so the minieyes namespace can enforce it with no exceptions (#37). Needs helm on PATH.

    uv run --no-project --with pytest --with pyyaml pytest tests/policy
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[2]
CHARTS = {
    "detector": "deploy/values/edge/detector.yaml",
    "triton": "deploy/values/edge/triton.yaml",
    "camera-sim": "deploy/values/edge/camera-sim.yaml",
    "event-api": "deploy/values/cloud/event-api.yaml",
}
POD_KINDS = {"Deployment", "StatefulSet", "Job", "DaemonSet"}

pytestmark = pytest.mark.skipif(not shutil.which("helm"), reason="helm not on PATH")


def rendered_pods():
    for chart, values in CHARTS.items():
        out = subprocess.run(
            ["helm", "template", chart, f"charts/{chart}", "-f", values, "--namespace", "minieyes"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for doc in yaml.safe_load_all(out):
            if doc and doc["kind"] in POD_KINDS:
                yield pytest.param(doc["spec"]["template"]["spec"], id=f"{chart}/{doc['kind']}")


PODS = list(rendered_pods()) if shutil.which("helm") else []


@pytest.mark.parametrize("pod", PODS)
def test_pod_meets_the_restricted_profile(pod):
    pod_ctx = pod.get("securityContext", {})
    assert not pod.get("hostNetwork") and not pod.get("hostPID") and not pod.get("hostIPC")
    assert not [v for v in pod.get("volumes", []) if "hostPath" in v]
    for c in pod.get("initContainers", []) + pod["containers"]:
        ctx = c.get("securityContext", {})
        name = c["name"]
        assert ctx.get("runAsNonRoot", pod_ctx.get("runAsNonRoot")) is True, name
        assert ctx.get("runAsUser", pod_ctx.get("runAsUser", 1)) != 0, name
        assert ctx.get("allowPrivilegeEscalation") is False, name
        assert not ctx.get("privileged"), name
        assert ctx.get("capabilities", {}).get("drop") == ["ALL"], name
        assert not set(ctx.get("capabilities", {}).get("add", [])) - {"NET_BIND_SERVICE"}, name
        seccomp = ctx.get("seccompProfile", pod_ctx.get("seccompProfile", {}))
        assert seccomp.get("type") in {"RuntimeDefault", "Localhost"}, name
        assert not [p for p in c.get("ports", []) if p.get("hostPort")], name
