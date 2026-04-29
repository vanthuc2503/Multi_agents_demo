import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = ROOT / "aws-agent-deploy"


def live_enabled() -> bool:
    return os.getenv("RUN_AWS_LIVE_TESTS") == "1"


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


def terraform_var_args() -> list[str]:
    name = os.getenv("EC2_TEST_INSTANCE_NAME") or f"agent-feasibility-{int(time.time())}"
    values = {
        "instance_name": name,
        "instance_type": os.getenv("EC2_TEST_INSTANCE_TYPE", "t3.micro"),
        "allowed_http_cidr": os.getenv("EC2_TEST_ALLOWED_HTTP_CIDR", "0.0.0.0/0"),
        "agent_api_key": os.getenv("AGENT_API_KEY", "dev-key-change-me-in-production"),
        "app_repository_url": os.getenv("EC2_TEST_APP_REPOSITORY_URL", ""),
        "app_repository_ref": os.getenv("EC2_TEST_APP_REPOSITORY_REF", ""),
    }
    args: list[str] = []
    for key, value in values.items():
        args.extend(["-var", f"{key}={value}"])
    return args


def terraform_outputs() -> dict:
    result = run_terraform("output", "-json")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def wait_for_health(url: str, timeout_seconds: int = 600) -> dict:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                if response.status == 200 and data.get("status") == "ok":
                    return data
        except Exception as exc:  # noqa: BLE001 - keep polling during bootstrap
            last_error = str(exc)
        time.sleep(10)
    raise AssertionError(f"{url} did not become healthy: {last_error}")


@pytest.mark.live
@pytest.mark.skipif(not live_enabled(), reason="set RUN_AWS_LIVE_TESTS=1 to create AWS resources")
def test_ec2_public_http_health_endpoint_is_reachable():
    init = run_terraform("init", "-input=false")
    assert init.returncode == 0, init.stdout + init.stderr

    var_args = terraform_var_args()
    apply = run_terraform("apply", "-auto-approve", "-input=false", *var_args)
    try:
        assert apply.returncode == 0, apply.stdout + apply.stderr

        outputs = terraform_outputs()
        health_url = outputs["health_url"]["value"]
        public_ip = outputs["public_ip"]["value"]

        assert health_url == f"http://{public_ip}/health"
        data = wait_for_health(
            health_url,
            timeout_seconds=int(os.getenv("EC2_TEST_HEALTH_TIMEOUT_SECONDS", "600")),
        )
        assert data["status"] == "ok"
    finally:
        destroy = run_terraform("destroy", "-auto-approve", "-input=false", *var_args)
        assert destroy.returncode == 0, destroy.stdout + destroy.stderr
