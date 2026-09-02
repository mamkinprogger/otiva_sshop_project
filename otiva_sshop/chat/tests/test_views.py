from unittest.mock import AsyncMock

import pytest

from chat.utils import MessageFromWebhook
from chat.views import assign_manager, manager_response_lag, identify_manager
import chat.views as views
from conftest import test_redis_client


@pytest.fixture
async def pd_redis_client(monkeypatch, test_redis_client):
    monkeypatch.setattr(
        views,
        "redis_client",
        test_redis_client
    )
    return test_redis_client


@pytest.fixture
def pd_redis_aclient_broker(monkeypatch, test_redis_aclient_broker):
    monkeypatch.setattr(
        views,
        "redis_aclient_broker",
        test_redis_aclient_broker,
    )
    return test_redis_aclient_broker


class TestAssignManager:
    async def test_assign_manager_selects_manager_by_load(self, monkeypatch):
        redis_mock = AsyncMock()
        redis_mock.hget.return_value = b"email21111@mail.ru"
        monkeypatch.setattr(
            views, "redis_client", redis_mock
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
            views, "redis_client", redis_mock
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
        (21111, "", r"manager_id without manager_email"),
        (0, "a@a.ru", r"load not passed"),
        (0, "", r"load not passed")
    ], ids=["manager_id without manager_email", "email without manager_id", "load not passed"])
    async def test_assign_manager_exceptions(self, monkeypatch, manger_id, manager_email, trace):
        redis_mock = AsyncMock()
        redis_mock.hget.return_value = b"email21111@mail.ru"
        monkeypatch.setattr(
            views, "redis_client", redis_mock
        )
        with pytest.raises(RuntimeError, match=trace):
            await assign_manager(manager_id=manger_id, manager_email=manager_email)


class TestManagerResponseLag:
    async def test_manager_response_lag(self, pd_redis_client, correct_message_factory):
        manager = 11111
        msg = MessageFromWebhook(correct_message_factory())
        msg.sending_time = 1_000_120
        expected_ttl = 60 * 60 * 24 * 3
        await pd_redis_client.set(msg.chat_id, f"{manager}:1000000", ex=expected_ttl)

        await manager_response_lag(msg)

        assert (await pd_redis_client.get(
            msg.chat_id
        )).decode() == f"{manager}:0"
        assert int(await pd_redis_client.ttl(
            msg.chat_id
        )) in range(expected_ttl - 5, expected_ttl + 5)
        assert await pd_redis_client.lrange(
            f"{manager}:response_lag", 0, -1
        ) == [b"2"]

    async def test_manager_response_lag_client_doesnt_waiting(self, pd_redis_client, correct_message_factory):
        manager = 11111
        msg = MessageFromWebhook(correct_message_factory())
        expected_ttl = 60 * 60 * 24 * 3
        await pd_redis_client.set(msg.chat_id, f"{manager}:0", ex=expected_ttl)

        await manager_response_lag(msg)

        assert int(await pd_redis_client.ttl(msg.chat_id)) in range(expected_ttl - 5, expected_ttl + 5)
        assert not await pd_redis_client.lrange(f"{manager}:response_lag", 0, -1)

    async def test_manager_response_lag_no_cached_chat(self, monkeypatch, correct_message_factory):
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        monkeypatch.setattr(views, "redis_client", redis_mock)

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
            pd_redis_client,
            correct_message_factory,
            sending_time,
            expect
    ):
        manager = 11111
        msg = MessageFromWebhook(correct_message_factory())
        expected_ttl = 60 * 60 * 24 * 3
        await pd_redis_client.set(msg.chat_id, f"{manager}:1000000", ex=expected_ttl)

        msg.sending_time = sending_time
        await manager_response_lag(msg)
        assert await pd_redis_client.lrange(
            f"{manager}:response_lag", 0, -1
        ) == expect


class TestIdentifyManager:
    @staticmethod
    def _celery_mock(monkeypatch):
        celery_mock = AsyncMock()
        celery_mock.delay.return_value = None
        monkeypatch.setattr(
            views, "send_message_to_manager", celery_mock
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
            pd_redis_client,
            pd_redis_aclient_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, None)

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis_client.hgetall("managers")

        await identify_manager(msg, managers)

        assert await pd_redis_client.hget("managers", 11111) == b"1"
        assert await pd_redis_client.hget("managers", 21111) == b"0"
        assert (await pd_redis_aclient_broker.lrange(11111, 0, -1))[0].split(b";")[1] == "new_chat=True".encode()
        assert await pd_redis_client.get(msg.chat_id) == f"11111:{msg.sending_time}".encode()

    async def test_client_in_creating_process(
            self,
            monkeypatch,
            pd_redis_client,
            pd_redis_aclient_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, None)

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis_client.hgetall("managers")
        await pd_redis_client.set(msg.chat_id, f"21111:{msg.sending_time - 20}")

        await identify_manager(msg, managers)

        assert await pd_redis_client.hget("managers", 11111) == b"0"
        assert await pd_redis_client.hget("managers", 21111) == b"0"
        assert (await pd_redis_aclient_broker.lrange(21111, 0, -1))[0].split(b";")[1] == "new_chat=False".encode()
        assert await pd_redis_client.get(msg.chat_id) == f"21111:{msg.sending_time - 20}".encode()

    async def test_cached_chat(
            self,
            monkeypatch,
            pd_redis_client,
            pd_redis_aclient_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 11111, "manager_email": "a@a.ru"})

        msg = MessageFromWebhook(correct_message_factory())
        await pd_redis_client.set(msg.chat_id, f"11111:{msg.sending_time - 20}")
        managers = await pd_redis_client.hgetall("managers")

        await identify_manager(msg, managers)

        assert await pd_redis_client.hget("managers", 11111) == b"0"
        assert await pd_redis_client.hget("managers", 21111) == b"0"
        assert await pd_redis_client.get(msg.chat_id) == f"11111:{msg.sending_time - 20}".encode()
        assert (await pd_redis_aclient_broker.lrange(11111, 0, -1))[0].split(b";")[1] == "new_chat=False".encode()

    async def test_cached_chat_new_question_from_client(
            self,
            monkeypatch,
            pd_redis_client,
            pd_redis_aclient_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 11111, "manager_email": "a@a.ru"})

        msg = MessageFromWebhook(correct_message_factory())
        await pd_redis_client.set(msg.chat_id, f"11111:0")
        managers = await pd_redis_client.hgetall("managers")

        await identify_manager(msg, managers)

        assert await pd_redis_client.hget("managers", 11111) == b"0"
        assert await pd_redis_client.hget("managers", 21111) == b"0"
        assert await pd_redis_client.get(msg.chat_id) == f"11111:{msg.sending_time}".encode()
        assert (await pd_redis_aclient_broker.lrange(11111, 0, -1))[0].split(b";")[1] == "new_chat=False".encode()

    async def test_cached_chat_expired(
            self,
            monkeypatch,
            pd_redis_client,
            pd_redis_aclient_broker,
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 21111, "manager_email": "a@a.ru"})

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis_client.hgetall("managers")

        await identify_manager(msg, managers)

        assert await pd_redis_client.hget("managers", 11111) == b"0"
        assert await pd_redis_client.hget("managers", 21111) == b"0"
        assert await pd_redis_client.get(msg.chat_id) == f"21111:{msg.sending_time}".encode()
        assert (await pd_redis_aclient_broker.lrange(21111, 0, -1))[0].split(b";")[1] == "new_chat=False".encode()

    async def test_clients_managers_conflict(self, monkeypatch, pd_redis_client, correct_message_factory):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": 21111, "manager_email": "a@a.ru"})
        redis_mock = AsyncMock()
        redis_mock.get.return_value = f"11111:1000000".encode()
        redis_broker_mock = AsyncMock()
        monkeypatch.setattr(views, "redis_client", redis_mock)
        monkeypatch.setattr(views, "redis_aclient_broker", redis_broker_mock)


        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis_client.hgetall("managers")

        with pytest.raises(views.ClientMessageError, match=r"!="):
            await identify_manager(msg, managers)

        redis_mock.get.assert_awaited_once_with(msg.chat_id)
        redis_broker_mock.lpush.assert_not_awaited()

    async def test_existing_client_open_a_chat(
            self, 
            monkeypatch, 
            pd_redis_client, 
            pd_redis_aclient_broker, 
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": None, "manager_email": None})

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis_client.hgetall("managers")

        await identify_manager(msg, managers)

        assert await pd_redis_client.hget("managers", 11111) == b"1"
        assert await pd_redis_client.hget("managers", 21111) == b"0"
        assert (await pd_redis_aclient_broker.lrange(11111, 0, -1))[0].split(b";")[1] == "new_chat=True".encode()
        assert await pd_redis_client.get(msg.chat_id) == f"11111:{msg.sending_time}".encode()

    async def test_existing_client_chatting_while_his_manager_updated(
            self,
            monkeypatch, 
            pd_redis_client,
            pd_redis_aclient_broker, 
            correct_message_factory
    ):
        self._celery_mock(monkeypatch)
        self._client_mock(monkeypatch, {"manager_id": None, "manager_email": None})

        msg = MessageFromWebhook(correct_message_factory())
        managers = await pd_redis_client.hgetall("managers")
        await pd_redis_client.set(msg.chat_id, f"11111:{msg.sending_time - 20}")

        await identify_manager(msg, managers)

        assert await pd_redis_client.hget("managers", 11111) == b"0"
        assert await pd_redis_client.hget("managers", 21111) == b"0"
        assert (await pd_redis_aclient_broker.lrange(11111, 0, -1))[0].split(b";")[1] == "new_chat=False".encode()
        assert await pd_redis_client.get(msg.chat_id) == f"11111:{msg.sending_time - 20}".encode()


class TestWebhook:
    @staticmethod
    def _get_url():
        return "http://localhost:8000/webhook/"

    @pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
    async def test_returns_404_for_non_post(self, async_client, method):
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
            pd_redis_client,
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
            pd_redis_client,
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


