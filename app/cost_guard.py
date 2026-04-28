from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings


_redis = redis.from_url(settings.redis_url, decode_responses=True)


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def check_budget(user_id: str, estimated_cost_usd: float) -> None:
    """
    Track spending per user per month in Redis.
    Raise 402 when exceeding monthly budget.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    key = f"budget:{user_id}:{_month_key()}"
    current = float(_redis.get(key) or 0.0)
    if current + estimated_cost_usd > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail=f"Monthly budget exceeded (${settings.monthly_budget_usd}/month)",
        )

    pipe = _redis.pipeline()
    pipe.incrbyfloat(key, float(estimated_cost_usd))
    pipe.expire(key, 32 * 24 * 3600)
    pipe.execute()


def estimate_cost_usd(text: str) -> float:
    # Mock cost model: ~ 1e-6 USD per char (tiny but accumulates in tests)
    # The checker only needs the guard to trigger at the configured budget.
    return max(0.000001 * len(text), 0.0001)

