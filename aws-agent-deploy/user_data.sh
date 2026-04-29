#!/usr/bin/env bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
AGENT_API_KEY="${agent_api_key}"
APP_REPOSITORY_URL="${app_repository_url}"
APP_REPOSITORY_REF="${app_repository_ref}"

apt-get update
apt-get install -y ca-certificates curl git docker.io docker-compose-plugin
systemctl enable --now docker

mkdir -p /opt/agent-feasibility
cd /opt/agent-feasibility

if [ -n "$APP_REPOSITORY_URL" ]; then
  git clone "$APP_REPOSITORY_URL" app
  cd app
  if [ -n "$APP_REPOSITORY_REF" ]; then
    git checkout "$APP_REPOSITORY_REF"
  fi
  cp .env.example .env || true
  {
    echo "AGENT_API_KEY=$AGENT_API_KEY"
    echo "REDIS_URL=redis://redis:6379/0"
    echo "ENVIRONMENT=staging"
    echo "ALLOWED_ORIGINS=*"
  } >> .env
  docker compose up -d --build
else
  cat > app.py <<'PY'
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="EC2 Feasibility Agent")


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ec2-feasibility-agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/ask")
def ask(
    body: AskRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
):
    if x_api_key != "${agent_api_key}":
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    if not x_openai_key:
        return {
            "user_id": body.user_id,
            "question": body.question,
            "answer": "Mock EC2 feasibility response.",
            "model": "mock",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "history_count": 0,
        }

    from openai import OpenAI

    client = OpenAI(api_key=x_openai_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": body.question}],
    )
    answer = response.choices[0].message.content or ""
    return {
        "user_id": body.user_id,
        "question": body.question,
        "answer": answer.strip(),
        "model": "gpt-4o-mini",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history_count": 0,
    }
PY

  cat > Dockerfile <<'DOCKER'
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.0 "uvicorn[standard]==0.30.0" pydantic==2.9.0 "openai>=1.0.0"
COPY app.py .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
DOCKER

  cat > compose.yaml <<'YAML'
services:
  agent:
    build: .
    ports:
      - "80:8000"
    restart: unless-stopped
YAML

  docker compose up -d --build
fi
