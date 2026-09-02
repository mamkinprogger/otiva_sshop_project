import pytest

from redis.asyncio import Redis
from redis import Redis as Redis_sync

from app.settings import REDIS_TEST, REDIS_TEST_BROKER


@pytest.fixture
async def test_redis_client():
    aredis_client = Redis.from_url(REDIS_TEST)

    managers_id = [11111, 21111]

    await aredis_client.hset(
        name="managers",
        mapping={i: 0 for i in managers_id},
    )

    await aredis_client.hset(
        name='emails_managers',
        mapping={i: f"email{i}@mail.ru" for i in managers_id}
    )

    yield aredis_client
    await aredis_client.flushdb()
    await aredis_client.aclose()

@pytest.fixture
def test_redis_client_broker():
    redis_client = Redis_sync.from_url(REDIS_TEST_BROKER)

    yield redis_client
    redis_client.flushdb()
    redis_client.close()



@pytest.fixture
async def test_redis_aclient_broker():
    redis_client = Redis.from_url(REDIS_TEST_BROKER)

    yield redis_client
    await redis_client.flushdb()
    await redis_client.aclose()
