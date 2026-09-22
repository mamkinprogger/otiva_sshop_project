from redis.asyncio import Redis
from redis import Redis as Redis_sync

from app.settings import REDIS_CLIENT, REDIS_BROKER

redis = Redis.from_url(REDIS_CLIENT)
aredis_broker = Redis.from_url(REDIS_BROKER)
redis_broker = Redis_sync.from_url(REDIS_BROKER)
