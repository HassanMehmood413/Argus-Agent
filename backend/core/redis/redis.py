import redis
from backend.config.settings import get_settings
from fastapi import Depends
from typing import Annotated

settings = get_settings()


redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
)


def get_redis_client():
    return redis_client

REDIS_CLIENT_DEP = Annotated[redis.Redis, Depends(get_redis_client)]
