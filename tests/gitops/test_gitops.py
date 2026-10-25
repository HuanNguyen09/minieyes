"""Invariants of the GitOps seed in gitops/ (#29). Needs helm on PATH for the render test.

uv run --no-project --with pytest --with pyyaml pytest tests/gitops
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[2]
GITOPS = ROOT / "gitops"
APP_REPO = "https://github.com/HuanNguyen09/minieyes.git"
GITOPS_REPO = "https://github.com/HuanNguyen09/minieyes-gitops.git"
PLACEHOLDERS = {"AWS_ACCOUNT_ID", "BASE_DOMAIN", "ACME_EMAIL", "EDGE_EIP", "ADMIN_CIDR"}
EXAMPLE = {
    "AWS_ACCOUNT_ID": "123456789012",
    "BASE_DOMAIN": "203-0-113-10.sslip.io",
    "ACME_EMAIL": "ops@example.com",
    "EDGE_EIP": "198.51.100.7",
    "ADMIN_CIDR": "203.0.113.0/28",
}
# chart -> value key holding the image reference whose tag must equal the chart revision
IMAGE_TAG = {
    "detector": ("image", "tag"),
    "event-api": ("image", "tag"),
    "camera-sim": ("image", "tag"),
    "triton": ("model", "image"),
}


def applications():
    return sorted(GITOPS.glob("*/*/apps/*.yaml"))


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def substitute(text: str) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: EXAMPLE[m.group(1)], text)


def app_repo_chart(app: dict) -> tuple[dict, list[str]] | None:
    """The app-repo chart source of an Application and its $values files, if it has one."""
    for source in app["spec"].get("sources", []):
        if source["repoURL"] == APP_REPO and source.get("path", "").startswith("charts/"):
            return source, source.get("helm", {}).get("valueFiles", [])
    return None


@pytest.mark.parametrize("path", applications(), ids=lambda p: p.stem)
def test_every_application_self_heals_and_prunes(path):
    app = load(path)

    assert (app["kind"], app["metadata"]["namespace"]) == ("Application", "argocd")
    assert app["spec"]["syncPolicy"]["automated"] == {"prune": True, "selfHeal": True}


@pytest.mark.parametrize("path", applications(), ids=lambda p: p.stem)
def test_every_referenced_file_and_path_exists(path):
    app = load(path)
    for source in app["spec"]["sources"]:
        if "path" in source and source["repoURL"] == APP_REPO:
            assert (ROOT / source["path"]).is_dir(), source["path"]
        for ref in source.get("helm", {}).get("valueFiles", []):
            repo_root, rel = ref.split("/", 1)
            base = {"$values": GITOPS, "$app": ROOT}[repo_root]
            assert (base / rel).is_file(), ref


@pytest.mark.parametrize("path", applications(), ids=lambda p: p.stem)
def test_minieyes_workloads_land_in_a_restricted_namespace(path):
    app = load(path)
    if app["spec"]["destination"]["namespace"] != "minieyes":
        pytest.skip("not a minieyes workload")
    labels = app["spec"]["syncPolicy"]["managedNamespaceMetadata"]["labels"]

    assert labels["pod-security.kubernetes.io/enforce"] == "restricted"


@pytest.mark.parametrize("path", applications(), ids=lambda p: p.stem)
def test_chart_revision_and_image_tag_are_the_same_commit(path):
    app = load(path)
    found = app_repo_chart(app)
    chart = found and found[0]["path"].removeprefix("charts/")
    if chart not in IMAGE_TAG:
        pytest.skip("no app-repo image")
    source, value_files = found
    values = load(GITOPS / value_files[0].removeprefix("$values/"))
    section, key = IMAGE_TAG[chart]
    image_ref = values[section][key]

    assert image_ref.rsplit(":", 1)[-1] == source["targetRevision"]
    assert re.fullmatch(r"[0-9a-f]{40}", source["targetRevision"])


def test_only_known_placeholders_are_used():
    used = set()
    for path in GITOPS.rglob("*.yaml"):
        used |= set(re.findall(r"\$\{(\w+)\}", path.read_text()))

    assert used <= PLACEHOLDERS


def test_each_root_points_at_its_own_apps_directory():
    for root in GITOPS.glob("*/*/root.yaml"):
        source = load(root)["spec"]["source"]
        assert source["repoURL"] == GITOPS_REPO
        assert source["path"] == f"{root.parent.relative_to(GITOPS).as_posix()}/apps"


@pytest.mark.skipif(not shutil.which("helm"), reason="helm not on PATH")
@pytest.mark.parametrize("path", applications(), ids=lambda p: p.stem)
def test_app_repo_charts_render_with_the_gitops_values(path, tmp_path):
    found = app_repo_chart(load(path))
    if found is None:
        pytest.skip("upstream chart or kustomize source")
    source, value_files = found
    args = []
    for i, ref in enumerate(value_files):
        rendered = tmp_path / f"values-{i}.yaml"
        rendered.write_text(substitute((GITOPS / ref.removeprefix("$values/")).read_text()))
        args += ["-f", str(rendered)]

    result = subprocess.run(
        ["helm", "template", path.stem, str(ROOT / source["path"]), *args],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
