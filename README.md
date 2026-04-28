# Production AI Agent API

A production-minded **FastAPI** service that exposes a single “ask” endpoint behind an **API key**, backed by **Redis** for:

- **Per-user rate limiting** (sliding window)
- **Per-user conversation history** (stateless app; history stored in Redis)
- **Per-user monthly budget guard** (returns HTTP 402 when exceeded)

It also includes:

- **Health + readiness probes** (`/health`, `/ready`)
- A lightweight **browser UI** at `/ui` to test a deployed backend
- **Docker multi-stage** build and **non-root** runtime
- Deploy configuration for **Railway** and **Render**

## Repository layout

```
.
├── app/
│   ├── main.py             # FastAPI app + endpoints + middleware logging
│   ├── config.py           # Settings from environment (12-factor)
│   ├── auth.py             # API key verification (X-API-Key)
│   ├── redis_client.py     # Redis client (lazy init + ping)
│   ├── rate_limiter.py     # Sliding-window rate limit (Redis ZSET)
│   └── cost_guard.py       # Monthly budget guard (Redis)
├── utils/
│   ├── openai_llm.py        # OpenAI call (chat.completions)
│   └── mock_llm.py          # Mock fallback when no OpenAI key is provided
├── web/
│   ├── index.html           # UI served at /ui
│   └── static/
│       ├── app.js
│       └── styles.css
├── nginx/
│   └── nginx.conf           # Local reverse proxy (port 80)
├── Dockerfile
├── docker-compose.yml       # Local stack: nginx + agent + redis
├── requirements.txt
├── .env.example
├── .dockerignore
├── railway.toml
├── render.yaml
└── check_production_ready.py
```

## Quickstart (Docker Compose)

### 1) Create local environment file

```bash
cp .env.example .env
```

Update `.env` at minimum:

- `AGENT_API_KEY` (required)
- `REDIS_URL` (compose uses `redis://redis:6379/0` by default)

### 2) Start the stack

```bash
docker compose up --build
```

Services:

- `redis`: stores rate-limit counters, conversation history, budget tracking
- `agent`: FastAPI app (internal `:8000`)
- `nginx`: public entrypoint on `http://localhost` (port 80)

### 3) Try it

```bash
curl http://localhost/health
curl http://localhost/ready
```

Send a request (PowerShell-friendly example):

```bash
curl -H "X-API-Key: dev-key-change-me-in-production" `
  -H "Content-Type: application/json" `
  -X POST http://localhost/ask `
  -d "{\"user_id\":\"test\",\"question\":\"hello\"}"
```

Open the UI:

- `http://localhost/ui`

## Running without Docker (optional)

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables (or create `.env` from `.env.example`) and run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Configuration

Configuration is read from environment variables (and `.env` locally).

- **`AGENT_API_KEY`**: required; requests to `/ask` must include `X-API-Key`
- **`REDIS_URL`**: required for `/ready` and `/ask` to work reliably
- **`OPENAI_API_KEY`**: optional; if empty, the service uses a mock responder
- **`LLM_MODEL`**: OpenAI model name (default: `gpt-4o-mini`)
- **`RATE_LIMIT_PER_MINUTE`**: per-user request limit (default: 10)
- **`MONTHLY_BUDGET_USD`**: per-user monthly budget guard (default: 10)
- **`HISTORY_MAX_MESSAGES`**: max Redis messages to prepend (default: 20)
- **`ALLOWED_ORIGINS`**: CORS allowlist (default: `*`)
- **`ENVIRONMENT`**: when set to `production`, `/docs` is disabled

### Supplying OpenAI credentials per request

You can send an OpenAI API key **per request** via `X-OpenAI-Key`. The service does not store it; it only uses it for that call.

## API

### `GET /`

Returns basic service info and available endpoints.

### `GET /health`

Liveness probe. Returns basic status, uptime, request counters, and whether Redis is currently reachable.

### `GET /ready`

Readiness probe. Returns `{"ready": true}` only when Redis is reachable.

### `GET /ui`

Minimal browser UI for testing: calls `/health`, `/ready`, and `/ask` using `fetch`.

### `POST /ask` (protected)

Headers:

- `X-API-Key: <AGENT_API_KEY>` (required)
- `X-OpenAI-Key: <openai_key>` (optional; overrides `OPENAI_API_KEY`)

Body:

```json
{ "user_id": "test", "question": "hello" }
```

Responses:

- `200`: returns `{ user_id, question, answer, model, timestamp, history_count }`
- `401`: missing/invalid API key
- `429`: rate limit exceeded
- `402`: monthly budget exceeded
- `503`: Redis unavailable

## Deployment

### Railway

- The service can be deployed directly from this repository using the included `Dockerfile`.
- Set environment variables:
  - `AGENT_API_KEY` (required)
  - `REDIS_URL` (required; typically provided by a Railway Redis add-on)
  - `OPENAI_API_KEY` (optional)

### Render

`render.yaml` provides a Docker-based service definition. You still need to provide:

- `AGENT_API_KEY`
- `REDIS_URL`
- `OPENAI_API_KEY` (optional)

## Production readiness checks

Run:

```bash
python check_production_ready.py
```

This script validates the presence of key files, basic security checks (like ignoring `.env`), and that the main operational endpoints exist in the code.
