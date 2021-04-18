import aioredis
import asyncio
from simple_settings import settings


class MyRedis(object):
    _redis = None
    _sem = asyncio.Semaphore(1)

    @classmethod
    async def redis(cls):
        if not cls._redis:
            async with cls._sem:
                if not cls._redis:
                    cls._redis = await aioredis.create_redis_pool(
                        (settings.REDIS_HOST, settings.REDIS_PORT),
                        db=1,
                        encoding="utf-8",
                        maxsize=1,
                    )
        return cls._redis
