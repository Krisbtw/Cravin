"""
Cravin — Rate Limiter Middleware
Sliding window rate limiting with Redis (Upstash/Vercel KV compatible) and local in-memory fallback.
"""

import time
from fastapi import HTTPException
import redis.asyncio as redis
from app.config import get_settings

settings = get_settings()

# Fallback to local memory if redis is not available
_local_cache = {}
redis_client = None

try:
    if settings.redis_url:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    else:
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
except Exception:
    redis_client = None


async def check_rate_limit(key: str, limit: int = 60, window_seconds: int = 60):
    """Sliding window rate limiter using Redis sorted sets with local fallback."""
    now = time.time()
    window_start = now - window_seconds

    if redis_client is None:
        # In-memory fallback
        if key not in _local_cache:
            _local_cache[key] = []
        _local_cache[key] = [t for t in _local_cache[key] if t > window_start]
        _local_cache[key].append(now)
        if len(_local_cache[key]) > limit:
            raise HTTPException(status_code=429, detail="Too Many Requests. Please slow down.")
        return

    try:
        pipeline = redis_client.pipeline()
        pipeline.zremrangebyscore(key, 0, window_start)
        pipeline.zadd(key, {str(now): now})
        pipeline.zcard(key)
        pipeline.expire(key, window_seconds)

        results = await pipeline.execute()
        request_count = results[2]

        if request_count > limit:
            raise HTTPException(status_code=429, detail="Too Many Requests. Please slow down.")
    except Exception:
        # In-memory fallback if Redis connection fails
        if key not in _local_cache:
            _local_cache[key] = []
        _local_cache[key] = [t for t in _local_cache[key] if t > window_start]
        _local_cache[key].append(now)
        if len(_local_cache[key]) > limit:
            raise HTTPException(status_code=429, detail="Too Many Requests. Please slow down.")
