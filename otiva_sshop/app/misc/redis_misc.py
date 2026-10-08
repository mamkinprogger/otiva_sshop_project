import uuid

from redis import Redis as Redis_sync
from redis.asyncio import Redis

from app.settings import REDIS_CLIENT, REDIS_BROKER

redis = Redis.from_url(REDIS_CLIENT)
aredis_broker = Redis.from_url(REDIS_BROKER)
redis_broker = Redis_sync.from_url(REDIS_BROKER)

class RedisLocker:
    def __init__(self, client: Redis):
        self.client = client

    def create_lock_key(self, prefix_lock_key: str, ttl=60) -> tuple[str, str] | None:
        """
        Try to create lock key.

        Return:
            (lock_key, lock_token) if lock key created,
            or
            None if key already exists.
        """
        lock_key = f"{prefix_lock_key}_lock"
        lock_token = str(uuid.uuid4())
        acquired = self.client.set(lock_key, lock_token, nx=True, ex=ttl)
        if not acquired:
            return None
        return lock_key, lock_token

    def release_locking(
            self,
            lock_data: tuple[str, str] | None = None,
            *,
            lock_key: str | None = None,
            lock_token: str | None = None
    ) -> None:
        """
        Delete lock_key if lock_key value is lock_token

        :param lock_data: (lock_key, lock_token)
        :param lock_key:
        :param lock_token:
        :return:
        """
        release_lock_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """
        if lock_data:
            self.client.eval(
                release_lock_script,
                1,
                *lock_data
            )
        else:
            self.client.eval(
                release_lock_script,
                1,
                lock_key,
                lock_token,
            )