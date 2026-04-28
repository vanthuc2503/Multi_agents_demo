"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting
  ✅ Cost guard
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, HTTPException, Depends, Request, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.redis_client import close_redis, get_redis, ping_redis
from app.cost_guard import check_budget, estimate_cost_usd

from utils.mock_llm import ask as mock_ask
from utils.openai_llm import ask as openai_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    _is_ready = ping_redis()
    logger.info(json.dumps({"event": "ready", "redis": _is_ready}))

    yield

    _is_ready = False
    close_redis()
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# Static UI (for testing deployed backend)
app.mount("/static", StaticFiles(directory="web/static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")] if settings.allowed_origins else ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-OpenAI-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128, description="User identifier for limits/budget/history")
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")

class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    timestamp: str
    history_count: int

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "ui": "GET /ui",
        },
    }


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse("web/index.html")


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`
    """
    r = get_redis()
    if r is None:
        raise HTTPException(
            status_code=503,
            detail="Redis unavailable. Set REDIS_URL (Railway) and redeploy.",
        )

    # Rate limit per user
    check_rate_limit(body.user_id)

    # Budget check (monthly)
    estimated = estimate_cost_usd(body.question)
    check_budget(body.user_id, estimated)

    logger.info(json.dumps({
        "event": "agent_call",
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    history_key = f"history:{body.user_id}"
    raw_history = r.lrange(history_key, -settings.history_max_messages, -1)
    history_count = len(raw_history)

    prompt = body.question
    if raw_history:
        # Keep it simple: prepend compact history to the question
        prompt = "Conversation so far:\n" + "\n".join(raw_history) + "\n\nUser: " + body.question

    openai_key = x_openai_key or settings.openai_api_key
    if openai_key:
        answer = openai_ask(api_key=openai_key, model=settings.llm_model, prompt=prompt)
        model_used = settings.llm_model
    else:
        answer = mock_ask(prompt)
        model_used = "mock"

    # Save to Redis (stateless)
    r.rpush(history_key, f"User: {body.question}")
    r.rpush(history_key, f"Assistant: {answer}")
    r.expire(history_key, 7 * 24 * 3600)

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=model_used,
        timestamp=datetime.now(timezone.utc).isoformat(),
        history_count=history_count,
    )


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    status = "ok"
    checks = {"redis": bool(get_redis() is not None), "llm": "openai" if settings.openai_api_key else "mock"}
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready or get_redis() is None:
        raise HTTPException(503, "Not ready")
    if not ping_redis():
        raise HTTPException(503, "Redis not ready")
    return {"ready": True}


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    global _is_ready
    logger.info(json.dumps({"event": "signal", "signum": signum}))
    _is_ready = False

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
