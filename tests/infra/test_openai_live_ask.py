import json
import os
import urllib.error
import urllib.request

import pytest


def openai_live_enabled() -> bool:
    return os.getenv("RUN_OPENAI_LIVE_TESTS") == "1"


@pytest.mark.openai_live
@pytest.mark.live
@pytest.mark.skipif(
    not openai_live_enabled(),
    reason="set RUN_OPENAI_LIVE_TESTS=1 to call OpenAI through a deployed agent",
)
def test_deployed_agent_can_call_openai_via_ask_endpoint():
    if not os.getenv("EC2_TEST_BASE_URL"):
        pytest.skip("set EC2_TEST_BASE_URL to the deployed agent base URL")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("set OPENAI_API_KEY to run the OpenAI live test")

    base_url = os.environ["EC2_TEST_BASE_URL"].rstrip("/")
    api_key = os.getenv("AGENT_API_KEY", "dev-key-change-me-in-production")
    openai_key = os.environ["OPENAI_API_KEY"]

    payload = json.dumps(
        {
            "user_id": "ec2-openai-live-test",
            "question": "Reply with exactly: ec2-openai-ok",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/ask",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "X-OpenAI-Key": openai_key,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"POST /ask failed with HTTP {exc.code}: {body}") from exc

    assert data["model"] != "mock"
    assert data["answer"]
