from __future__ import annotations

import logging
from typing import Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Lazy singleton Redis client. Returns None if connect/ping fails."""
    global _redis
    if _redis is not None:
        return _redis
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _redis = client
        return _redis
    except Exception as e:
        logger.error('{"event":"redis_unavailable","detail":"%s"}', str(e))
        _redis = None
        return None


def ping_redis() -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def close_redis() -> None:
    global _redis
    try:
        if _redis is not None:
            _redis.close()
    finally:
        _redis = None
