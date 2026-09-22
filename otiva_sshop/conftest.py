import pytest

from redis.asyncio import Redis
from redis import Redis as Redis_sync

from app.settings import REDIS_TEST, REDIS_TEST_BROKER


@pytest.fixture
async def test_redis():
    aredis = Redis.from_url(REDIS_TEST)

    managers_id = [11111, 21111]

    await aredis.hset(
        name="managers",
        mapping={i: 0 for i in managers_id},
    )

    await aredis.hset(
        name='emails_managers',
        mapping={i: f"email{i}@mail.ru" for i in managers_id}
    )

    yield aredis
    await aredis.flushdb()
    await aredis.aclose()

@pytest.fixture
def test_redis_broker():
    redis = Redis_sync.from_url(REDIS_TEST_BROKER)

    yield redis
    redis.flushdb()
    redis.close()



@pytest.fixture
async def test_aredis_broker():
    redis = Redis.from_url(REDIS_TEST_BROKER)

    yield redis
    await redis.flushdb()
    await redis.aclose()
