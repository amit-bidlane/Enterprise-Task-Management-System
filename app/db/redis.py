from collections.abc import AsyncGenerator

from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()


async def get_redis_client() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
