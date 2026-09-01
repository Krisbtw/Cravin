import time
from fastapi import HTTPException
import redis.asyncio as redis

# Fallback to local memory if redis is not available
_local_cache = {}

try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
except Exception:
    redis_client = None

async def check_rate_limit(key: str, limit: int, window_seconds: int):
    """Sliding window rate limiter using Redis sorted sets."""
    now = time.time()
    window_start = now - window_seconds
    
    if redis_client is None:
        # Fallback simplistic rate limiter
        if key not in _local_cache:
            _local_cache[key] = []
        _local_cache[key] = [t for t in _local_cache[key] if t > window_start]
        _local_cache[key].append(now)
        if len(_local_cache[key]) > limit:
            raise HTTPException(status_code=429, detail="Too Many Requests")
        return

    try:
        pipeline = redis_client.pipeline()
        # Remove old entries
        pipeline.zremrangebyscore(key, 0, window_start)
        # Add current request
        pipeline.zadd(key, {str(now): now})
        # Count requests in window
        pipeline.zcard(key)
        # Set TTL for cleanup
        pipeline.expire(key, window_seconds)
        
        results = await pipeline.execute()
        request_count = results[2]
        
        if request_count > limit:
            raise HTTPException(status_code=429, detail="Too Many Requests")
    except redis.ConnectionError:
        # Fail open or use local cache if redis is down
        pass
