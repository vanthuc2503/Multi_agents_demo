import shutil
import subprocess
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = ROOT / "aws-agent-deploy"


def run_terraform(*args: str) -> subprocess.CompletedProcess[str]:
    if not shutil.which("terraform"):
        pytest.skip("terraform CLI is not installed")
    return subprocess.run(
        ["terraform", *args],
        cwd=TERRAFORM_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.infra
def test_terraform_is_formatted():
    result = run_terraform("fmt", "-check")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.infra
def test_terraform_init_without_backend_passes():
    result = run_terraform("init", "-backend=false", "-input=false")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.infra
def test_terraform_validate_passes():
    init = run_terraform("init", "-backend=false", "-input=false")
    assert init.returncode == 0, init.stdout + init.stderr

    result = run_terraform("validate")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.infra
def test_terraform_plan_passes():
    has_aws_config = any(
        os.getenv(name)
        for name in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_WEB_IDENTITY_TOKEN_FILE")
    )
    if os.getenv("RUN_AWS_PLAN_TESTS") != "1" and not has_aws_config:
        pytest.skip("set AWS credentials or RUN_AWS_PLAN_TESTS=1 to run terraform plan")

    init = run_terraform("init", "-backend=false", "-input=false")
    assert init.returncode == 0, init.stdout + init.stderr

    result = run_terraform("plan", "-input=false", "-lock=false")
    assert result.returncode == 0, result.stdout + result.stderr
