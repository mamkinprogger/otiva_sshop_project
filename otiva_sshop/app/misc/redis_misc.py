from redis.asyncio import Redis
from redis import Redis as Redis_sync

from app.settings import REDIS_CLIENT

redis_client_task = Redis_sync.from_url(REDIS_CLIENT)
redis_client = Redis.from_url(REDIS_CLIENT)
