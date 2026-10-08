from app.misc.redis_misc import RedisLocker


class TestReleaseLocking:
    def test_worker_running(self, test_redis_broker):
        manager_key = "11111"
        locker = RedisLocker(test_redis_broker)
        locker.create_lock_key(manager_key)
        lock = locker.create_lock_key(manager_key)

        assert lock is None

    def test_worker_freeze(self, test_redis_broker):
        manager_key = "11111"

        # Worker A gets the lock.
        locker = RedisLocker(test_redis_broker)
        lock_key, old_token = locker.create_lock_key(manager_key)
        # Worker A is processing the message.....
        # Worker A's lock expires.
        test_redis_broker.delete(lock_key)

        # Worker B starts processing the same manager
        lock_key, new_token = locker.create_lock_key(manager_key)

        # Worker A thawed out
        locker.release_locking(lock_key=lock_key, lock_token=old_token)
        assert test_redis_broker.get(lock_key) == new_token.encode()
