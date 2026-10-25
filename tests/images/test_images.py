"""Image contract (#18). Needs Docker and the images built from the repo root:

    docker build -f apps/detector/Dockerfile -t minieyes-detector:dev .
    docker build -f apps/event-api/Dockerfile -t minieyes-event-api:dev .
    uv run --no-project --with pytest pytest tests/images -m integration

IMAGE_TAG overrides the tag (CI uses the git SHA). hadolint and trivy must be on PATH.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
TAG = os.environ.get("IMAGE_TAG", "dev")
IMAGES = {"detector": f"minieyes-detector:{TAG}", "event-api": f"minieyes-event-api:{TAG}"}
MAX_DETECTOR_BYTES = 500 * 1000 * 1000

pytestmark = pytest.mark.integration


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **kwargs,
    )


@pytest.mark.parametrize("service", IMAGES)
def test_image_runs_as_a_non_root_uid(service):
    result = run("docker", "run", "--rm", "--entrypoint", "id", IMAGES[service], "-u")

    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) != 0


def test_detector_image_is_under_500_mb_uncompressed():
    sizes = run("docker", "history", "--human=false", "--format", "{{.Size}}", IMAGES["detector"])

    assert sizes.returncode == 0, sizes.stderr
    assert sum(int(s) for s in sizes.stdout.split()) < MAX_DETECTOR_BYTES


@pytest.mark.skipif(not shutil.which("hadolint"), reason="hadolint not on PATH")
def test_dockerfiles_pass_hadolint_without_warnings():
    dockerfiles = sorted(str(p) for p in ROOT.glob("*/**/Dockerfile") if ".claude" not in p.parts)

    result = run("hadolint", "--failure-threshold", "warning", *dockerfiles)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(not shutil.which("trivy"), reason="trivy not on PATH")
@pytest.mark.parametrize("service", IMAGES)
def test_image_has_no_critical_vulnerabilities(service):
    result = run(
        "trivy",
        "image",
        "--quiet",
        "--severity",
        "CRITICAL",
        "--ignore-unfixed",
        "--exit-code",
        "1",
        IMAGES[service],
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_build_context_excludes_tests_models_videos_and_secrets():
    probe = "FROM busybox:1.37\nCOPY . /ctx\nRUN find /ctx -type f | sort > /files.txt\n"
    build = run(
        "docker",
        "build",
        "-q",
        "-t",
        "minieyes-context-probe",
        "-f",
        "-",
        ".",
        input=probe,
        cwd=ROOT,
    )
    assert build.returncode == 0, build.stderr
    listing = run("docker", "run", "--rm", "minieyes-context-probe", "cat", "/files.txt")
    run("docker", "rmi", "-f", "minieyes-context-probe")

    files = listing.stdout.split()
    assert files, listing.stderr
    forbidden = (".onnx", ".pt", ".mp4", ".tfstate", ".env", ".pem")
    assert not [f for f in files if f.endswith(forbidden)]
    assert not [f for f in files if "/tests/" in f or "/.git/" in f or "/infra/" in f]
    assert "/ctx/apps/detector/src/minieyes_detector/pipeline.py" in files
