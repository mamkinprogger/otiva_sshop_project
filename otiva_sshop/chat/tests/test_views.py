import pickle
from unittest.mock import AsyncMock, MagicMock

import pytest

import chat.views as views
from chat.utils import MessageFromWebhook
from chat.views import assign_manager, manager_response_lag, identify_manager, get_client_creating
from conftest import test_redis


@pytest.fixture
def logger_off(mocker):
    turn_off = mocker.patch("chat.views.logger")
    return turn_off

@pytest.fixture
async def pd_redis(monkeypatch, test_redis):
    monkeypatch.setattr(
        views,
        "redis",
        test_redis
    )
    return test_redis


@pytest.fixture
def pd_aredis_broker(monkeypatch, test_aredis_broker):
    monkeypatch.setattr(
        views,
        "aredis_broker",
        test_aredis_broker,
    )
    return test_aredis_broker


class TestAssignManager:
    async def test_assign_manager_selects_manager_by_load(self, monkeypatch):
        redis_mock = AsyncMock()
        redis_mock.hget.return_value = b"email21111@mail.ru"
        monkeypatch.setattr(
            views, "redis", redis_mock
        )

        result = await assign_manager(
            managers_load={
                b"11111": b"10",
                b"21111": b"5",
            }
        )
        assert result == (b"21111", b"email21111@mail.ru")
        redis_mock.hget.assert_awaited_once_with(
            "emails_managers",
            b"21111",
        )

    async def test_assign_manager_selects_manager_by_known_information(self, monkeypatch):
        redis_mock = AsyncMock()
        redis_mock.hget.return_value = b"email21111@mail.ru"
        monkeypatch.setattr(
            views, "redis", redis_mock
        )

        result_1 = await assign_manager(
            manager_id=21111,
            manager_email="email21111@mail.ru",
            managers_load={
                b"11111": b"10",
                b"21111": b"5",
            })
        result_2 = await assign_manager(
            manager_id=21111,
            manager_email="email21111@mail.ru",
            )
        assert result_1 == (b"21111", b"email21111@mail.ru")
        assert result_2 == (b"21111", b"email21111@mail.ru")
        redis_mock.hget.assert_not_awaited()

    @pytest.mark.parametrize("manger_id, manager_email, trace", [
        (21111, "", r"without manager_email"),
        (0, "a@a.ru", r"load not passed"),
        (0, "", r"load not passed")
    ], ids=["manager_id without manager_email", "email without manager_id", "load not passed"])
    async def test_assign_manager_exceptions(self, monkeypatch, manger_id, manager_email, trace):
        redis_mock = AsyncMock()
        redis_mock.hget.return_value = b"email21111@mail.ru"
        monkeypatch.setattr(
            views, "redis", redis_mock
        )
        with pytest.raises(RuntimeError, match=trace):
            await assign_manager(manager_id=manger_id, manager_email=manager_email)


class TestManagerResponseLag:
    async def test_manager_response_lag(self, pd_redis, correct_message_factory):
        manager = 11111
        msg = MessageFromWebhook(correct_message_factory())
        msg.sending_time = 1_000_120
        expected_ttl = 60 * 60 * 24 * 3
        await pd_redis.set(msg.chat_id, f"{manager}:1000000", ex=expected_ttl)

        await manager_response_lag(msg)

        assert (await pd_redis.get(
            msg.chat_id
        )).decode() == f"{manager}:0"
        assert int(await pd_redis.ttl(
            msg.chat_id
        )) in range(expected_ttl - 5, expected_ttl + 5)
        assert await pd_redis.lrange(
            f"{manager}:response_lag", 0, -1
        ) == [b"2"]

    async def test_manager_response_lag_client_doesnt_waiting(self, pd_redis, correct_message_factory):
        manager = 11111
        msg = MessageFromWebhook(correct_message_factory())
        expected_ttl = 60 * 60 * 24 * 3
        await pd_redis.set(msg.chat_id, f"{manager}:0", ex=expected_ttl)

        await manager_response_lag(msg)

        assert int(await pd_redis.ttl(msg.chat_id)) in range(expected_ttl - 5, expected_ttl + 5)
        assert not await pd_redis.lrange(f"{manager}:response_lag", 0, -1)

    async def test_manager_response_lag_no_cached_chat(self, monkeypatch, correct_message_factory):
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        monkeypatch.setattr(views, "redis", redis_mock)

        msg = MessageFromWebhook(correct_message_factory())
        await manager_response_lag(msg)

        redis_mock.get.assert_awaited_once_with(msg.chat_id)
        redis_mock.set.assert_not_awaited()
        redis_mock.lpush.assert_not_awaited()

    @pytest.mark.parametrize("sending_time, expect", [
        (999880, [b"2"]),
        (1000001, []),
        (1000061, [b"1"]),
    ], ids=["negative timedelta", "timedelta less then 1 min", "1 min lag"], )
    async def test_manager_response_lag_timethinghs(
            self,
            pd_redis,
            correct_message_factory,
            sending_time,
            expect
    ):
        manager = 11111
        msg = MessageFromWebhook(correct_message_factory())
        expected_ttl = 60 * 60 * 24 * 3
        await pd_redis.set(msg.chat_id, f"{manager}:1000000", ex=expected_ttl)

        msg.sending_time = sending_time
        await manager_response_lag(msg)
        assert await pd_redis.lrange(
            f"{manager}:response_lag", 0, -1
        ) == expect


class TestIdentifyManager:
    @staticmethod
    def _celery_mock(monkeypatch):
        celery_mock = MagicMock()
        celery_mock.delay.return_value = None
        monkeypatch.setattr(
            views, "send_notification_task", celery_mock
        )
        return celery_mock

    @staticmethod
    def _client_mock(monkeypatch, value):
        get_client_mock = AsyncMock()
        get_client_mock.return_value = value
        monkeypatch.setattr(
            views, "orm_contact_info_manager_from_client", get_client_mock
        )

    async def test_identify_manager_new_client(
            self,
            monkeypatch,
            pd_redis,
            pd_aredis_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, None)

        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())

        managers = await pd_redis.hgetall("managers")

        await identify_manager(msg, managers)

        msgs_in_queue = await pd_aredis_broker.lrange(11111, 0, -1)
        assert len(msgs_in_queue) == 1
        assert msgs_in_queue[0] == msg_to_queue
        assert await pd_redis.get(msg.chat_id) == f"11111:{msg.sending_time}".encode()

    async def test_client_in_creating_process(
            self,
            monkeypatch,
            pd_redis,
            pd_aredis_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, None)
        manager = 21111

        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        managers = await pd_redis.hgetall("managers")
        await pd_redis.set(msg.chat_id, f"{manager}:{msg.sending_time - 20}")
        await pd_aredis_broker.lpush(manager, msg_to_queue)

        await identify_manager(msg, managers)

        msgs_in_queue = await pd_aredis_broker.lrange(21111, 0, -1)
        assert len(msgs_in_queue) == 2
        assert msgs_in_queue[0] == msg_to_queue
        assert await pd_redis.get(msg.chat_id) == f"21111:{msg.sending_time - 20}".encode()

    async def test_cached_chat(
            self,
            monkeypatch,
            pd_redis,
            pd_aredis_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 11111, "manager_email": "a@a.ru"})

        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        await pd_redis.set(msg.chat_id, f"11111:{msg.sending_time - 20}")
        managers = await pd_redis.hgetall("managers")

        await identify_manager(msg, managers)

        msgs_in_queue = await pd_aredis_broker.lrange(11111, 0, -1)
        assert len(msgs_in_queue) == 1
        assert msgs_in_queue[0] == msg_to_queue
        assert await pd_redis.get(msg.chat_id) == f"11111:{msg.sending_time - 20}".encode()

    async def test_cached_chat_new_question_from_client(
            self,
            monkeypatch,
            pd_redis,
            pd_aredis_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 11111, "manager_email": "a@a.ru"})

        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        await pd_redis.set(msg.chat_id, f"11111:0")
        managers = await pd_redis.hgetall("managers")

        await identify_manager(msg, managers)

        assert await pd_redis.get(msg.chat_id) == f"11111:{msg.sending_time}".encode()
        msgs_in_queue = await pd_aredis_broker.lrange(11111, 0, -1)
        assert len(msgs_in_queue) == 1
        assert msgs_in_queue[0] == msg_to_queue

    async def test_cached_chat_expired(
            self,
            monkeypatch,
            pd_redis,
            pd_aredis_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 21111, "manager_email": "a@a.ru"})

        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        managers = await pd_redis.hgetall("managers")

        await identify_manager(msg, managers)

        msgs_in_queue = await pd_aredis_broker.lrange(21111, 0, -1)
        assert len(msgs_in_queue) == 1
        assert msgs_in_queue[0] == msg_to_queue
        assert await pd_redis.get(msg.chat_id) == f"21111:{msg.sending_time}".encode()

    async def test_clients_managers_conflict(self, monkeypatch, pd_redis, correct_message_factory, mocker, logger_off):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 21111, "manager_email": "a@a.ru"})
        mocker.patch("chat.views.get_client_creating", return_value=None)
        redis_broker_mock = AsyncMock()
        monkeypatch.setattr(views, "aredis_broker", redis_broker_mock)

        msg = MessageFromWebhook(correct_message_factory())
        await pd_redis.set(msg.chat_id, "11111:1000000")
        managers = await pd_redis.hgetall("managers")

        with pytest.raises(views.ClientMessageError, match=r"!="):
            await identify_manager(msg, managers)

        redis_broker_mock.lpush.assert_not_awaited()

    async def test_existing_client_open_a_chat(
            self,
            monkeypatch,
            pd_redis,
            pd_aredis_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": None, "manager_email": None})

        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        managers = await pd_redis.hgetall("managers")

        await identify_manager(msg, managers)

        msgs_in_queue = await pd_aredis_broker.lrange(11111, 0, -1)
        assert len(msgs_in_queue) == 1
        assert msgs_in_queue[0] == msg_to_queue
        assert await pd_redis.get(msg.chat_id) == f"11111:{msg.sending_time}".encode()

    async def test_existing_client_chatting_while_his_manager_updated(
            self,
            monkeypatch,
            pd_redis,
            pd_aredis_broker,
            correct_message_factory,
            logger_off
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": None, "manager_email": None})

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis.hgetall("managers")
        await pd_redis.set(msg.chat_id, f"11111:{msg.sending_time - 20}")
        await pd_aredis_broker.lpush("11111:processing", pickle.dumps(msg.create()))

        await identify_manager(msg, managers)

        assert await pd_redis.get(msg.chat_id) == f"11111:{msg.sending_time - 20}".encode()

    async def test_chat_open_but_client_not_exists(self, monkeypatch, pd_redis, correct_message_factory):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, None)

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis.hgetall("managers")
        await pd_redis.set(msg.chat_id, f"11111:{msg.sending_time}")

        with pytest.raises(views.ClientMessageError, match=r"client is open"):
            await identify_manager(msg, managers)

    async def test_client_with_no_manager_writing_in_existing_chat(self, monkeypatch, pd_redis, pd_aredis_broker, correct_message_factory):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": None, "manager_email": None})

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis.hgetall("managers")
        await pd_redis.set(msg.chat_id, f"11111:{msg.sending_time}")

        with pytest.raises(views.ClientMessageError, match=r"cannot write"):
            await identify_manager(msg, managers)


class TestGetClientCreating:
    async def test_in_pending(self, pd_aredis_broker, correct_message_factory):
        manager = b"11111"
        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        await pd_aredis_broker.lpush(manager, msg_to_queue)

        result = await get_client_creating(manager, msg.chat_id)

        assert result is True

    async def test_in_processing(self, pd_aredis_broker, correct_message_factory):
        manager = "11111"
        proc_key = f"{manager}:processing"
        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        await pd_aredis_broker.lpush(proc_key, msg_to_queue)

        result = await get_client_creating(manager.encode(), msg.chat_id)

        assert result is True

    async def test_not_in_queues(self, pd_aredis_broker, correct_message_factory):
        manager = b"11111"
        msg = MessageFromWebhook(correct_message_factory())
        msg_to_queue = pickle.dumps(msg.create())
        await pd_aredis_broker.lpush(manager, msg_to_queue)

        msg2 = MessageFromWebhook(correct_message_factory())
        result = await get_client_creating(manager, msg2.chat_id)

        assert result is False

    async def test_chat_id_in_text(self, pd_aredis_broker, correct_message_factory):
        manager = b"11111"
        msg = MessageFromWebhook(correct_message_factory())
        msg2 = MessageFromWebhook(correct_message_factory())

        msg.text = f"~chat_id:{msg2.chat_id}~"
        msg_to_queue = pickle.dumps(msg.create())
        await pd_aredis_broker.lpush(manager, msg_to_queue)

        result = await get_client_creating(manager, msg2.chat_id)

        assert result is False


class TestWebhook:
    @staticmethod
    def _get_url():
        return "http://localhost:8000/webhook/"

    @pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
    async def test_returns_404_for_non_post(self, async_client, method, logger_off):
        response = await getattr(async_client, method.lower())(self._get_url())
        assert response.status_code == 404

    async def test_no_message(self, monkeypatch, async_client):
        message_lag_mock = AsyncMock()
        monkeypatch.setattr(views, "manager_response_lag", message_lag_mock)
        identify_manager_mock = AsyncMock()
        monkeypatch.setattr(views, "identify_manager", identify_manager_mock)

        data = {
            "payload": {
                "type": "message",
                "value": {}
            },
        }

        response = await async_client.post(self._get_url(), data=data, content_type="application/json")

        assert response.status_code == 200
        message_lag_mock.assert_not_awaited()
        identify_manager_mock.assert_not_awaited()


    @pytest.mark.parametrize("sender", [
        11111,
        253428356
    ], ids=["manager_id", "store_id"])
    async def test_manager_send_message(
            self,
            monkeypatch,
            async_client,
            pd_redis,
            correct_message_factory,
            sender
    ):
        monkeypatch.setattr(views, "AVITO_STORE_ID", 253428356)
        message_lag_mock = AsyncMock()
        monkeypatch.setattr(views, "manager_response_lag", message_lag_mock)
        identify_manager_mock = AsyncMock()
        monkeypatch.setattr(views, "identify_manager", identify_manager_mock)

        msg = correct_message_factory()
        msg["author_id"] = sender
        data = {
            "payload": {
                "type": "message",
                "value": msg
                },
            }
        response = await async_client.post(self._get_url(), data=data, content_type="application/json")

        assert response.status_code == 200
        message_lag_mock.assert_awaited_once()
        identify_manager_mock.assert_not_awaited()

    async def test_client_send_message(
            self,
            monkeypatch,
            async_client,
            pd_redis,
            correct_message_factory,
    ):
        message_lag_mock = AsyncMock()
        monkeypatch.setattr(views, "manager_response_lag", message_lag_mock)
        identify_manager_mock = AsyncMock()
        monkeypatch.setattr(views, "identify_manager", identify_manager_mock)

        msg = correct_message_factory()
        msg["author_id"] = 23451
        data = {
            "payload": {
                "type": "message",
                "value": msg
                },
            }
        response = await async_client.post(self._get_url(), data=data, content_type="application/json")

        assert response.status_code == 200
        identify_manager_mock.assert_awaited_once()
        message_lag_mock.assert_not_awaited()


