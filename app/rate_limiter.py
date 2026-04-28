import time

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_redis


def check_rate_limit(user_id: str) -> None:
    """
    Sliding window rate limit using Redis sorted set.
    Limit: settings.rate_limit_per_minute requests per 60s per user.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    client = get_redis()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Redis unavailable. Set REDIS_URL (Railway) and redeploy.",
        )

    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - 60_000
    key = f"rate:{user_id}"

    try:
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start_ms)
        pipe.zadd(key, {str(now_ms): now_ms})
        pipe.zcard(key)
        pipe.expire(key, 120)
        _removed, _added, count, _ttl = pipe.execute()
    except redis.exceptions.RedisError as e:
        raise HTTPException(status_code=503, detail=f"Redis error: {e}")

    if int(count) > settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min",
            headers={"Retry-After": "60"},
        )


def ping_redis() -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False

