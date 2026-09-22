from smtplib import SMTPException

import pytest

from chat.tests.conftest import correct_message_factory
from chat.utils import MessageFromWebhook
from conftest import test_redis_broker

from chat.tasks import choose_messages, send_manager
import chat.tasks as tasks

@pytest.fixture
def pd_redis(monkeypatch, test_redis):
    monkeypatch.setattr(
        tasks,
        "redis",
        test_redis
    )
    return test_redis

@pytest.fixture
def pd_redis_broker(monkeypatch, test_redis_broker):
    monkeypatch.setattr(
        tasks,
        "redis_broker",
        test_redis_broker,
    )
    return test_redis_broker


@pytest.fixture
def add_msg_for_manager(test_redis_broker, correct_message_factory):
    input_message = correct_message_factory(item_id=True)
    broker = test_redis_broker

    def add_msg(
            manager_id: int | str,
            new_chat: bool = False,
            message=input_message,
    ) -> None:
        target_manager = str(manager_id)
        msg = MessageFromWebhook(message)

        msg_to_queue = f"{new_chat=};{msg.create_str()}"
        broker.lpush(target_manager, msg_to_queue)

    return add_msg


class TestChooseMessages:
    def test_one_message(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        manager_id = 11111
        manager_key = str(manager_id)
        msg = correct_message_factory(item_id=True)
        add_msg_for_manager(manager_id, new_chat=True, message=msg)
        msg_entity = MessageFromWebhook(msg).create()

        messages = choose_messages(manager_key)

        assert len(messages) == 1
        assert pd_redis_broker.llen(manager_key) == 0
        assert isinstance(messages, list)
        assert isinstance(messages[0], dict)
        for i in msg_entity:
            assert msg_entity[i] == messages[0].get(i)
        assert isinstance(messages[0].get("new_chat"), bool)

    def test_different_messages(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        manager_id  = 11111
        manager_key = str(manager_id)
        msgs = []
        for i in range(5):
            msg = correct_message_factory(item_id=bool(i % 2))
            add_msg_for_manager(manager_key, bool(i % 2), msg)
            msgs.append(MessageFromWebhook(msg))

        messages = choose_messages(manager_key)

        assert len(messages) == 5
        assert pd_redis_broker.llen(manager_key) == 0
        assert isinstance(messages, list)
        for i in messages:
            assert isinstance(i, dict)

    def test_max_messages_from_one_chat(self, add_msg_for_manager, pd_redis_broker):
        manager_id = 11111
        manager_key = str(manager_id)
        for i in range(5):
            add_msg_for_manager(manager_key, bool(i % 2))

        messages = choose_messages(manager_key)

        assert len(messages) == 2
        assert pd_redis_broker.llen(manager_key) == 0

    def test_many_messages_from_different_chats(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        manager_id = 11111
        manager_key = str(manager_id)

        for i in range(3):
            msg = correct_message_factory(item_id=bool(i % 2))
            add_msg_for_manager(manager_key, bool(i % 2), msg)
            for j in range(i):
                add_msg_for_manager(manager_key, bool(j % 2), msg)

        messages = choose_messages(manager_key)

        assert len(messages) == 5
        assert pd_redis_broker.llen(manager_key) == 0

    def test_already_read_msg(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        manager_id = 11111
        manager_key = str(manager_id)
        msg = correct_message_factory(read=True)

        add_msg_for_manager(manager_key, message=msg)

        messages = choose_messages(manager_key)

        assert len(messages) == 0
        assert pd_redis_broker.llen(manager_key) == 0

    def test_no_messages(self):
        manager_id = 11111
        manager_key = str(manager_id)

        messages = choose_messages(manager_key)

        assert len(messages) == 0


class TestSendManager:
    def test_success_one_sending(self, mocker):
        manager_id = 11111
        manager_key = str(manager_id)
        msg = {
            "client_id": 334,
            "topic": "AvotTAK:Аноним",
            "prev_email": None
        }

        create_msgsdata_mock = mocker.patch(
            "chat.tasks.create_msgsdata_for_email",
            return_value = {0: msg}
        )
        send_notifications_mock = mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[0, True]]
        )

        results = send_manager(manager_id, "asd@.ru", manager_key)

        assert len(results) == 0
        create_msgsdata_mock.assert_called_once()
        send_notifications_mock.assert_called_once_with(
            "asd@.ru",
            emails_data=[(334, "AvotTAK:Аноним", None)],
            alias_keys=[0],
            view_result=True
        )

    def test_success_many_sending(self, mocker):
        manager_id = 11111
        manager_key = str(manager_id)
        msgs = [{
            "client_id": 334 + i,
            "topic": "AvotTAK:Аноним",
            "prev_email": None
        } for i in range(3)]

        mocker.patch(
            "chat.tasks.create_msgsdata_for_email",
            return_value={n: msg for n, msg in enumerate(msgs)}
        )
        mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[i, True] for i in range(len(msgs))]
        )

        results = send_manager(manager_id, "asd@.ru", manager_key)

        assert len(results) == 0

    def test_fail_one_unexpected_err_sending(self, mocker):
        manager_id = 11111
        manager_key = str(manager_id)
        msgs = [{
            "client_id": 333,
            "topic": "AvotTAK:Аноним",
            "prev_email": None
        }]

        mocker.patch(
            "chat.tasks.create_msgsdata_for_email",
            return_value={n: msg for n, msg in enumerate(msgs)}
        )
        mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[i, False, RuntimeError()] for i in range(len(msgs))]
        )

        results = send_manager(manager_id, "asd@.ru", manager_key)

        assert len(results) == 0

    def test_fail_smtperr_sending(self, mocker, correct_message_factory):
        manager_id = 11111
        manager_key = str(manager_id)

        msgs = [{
            "client_id": 333,
            "topic": "AvotTAK:Аноним",
            "prev_email": None,
            "new_chat": True,
        }]

        mocker.patch(
            "chat.tasks.create_msgsdata_for_email",
            return_value={n: msg for n, msg in enumerate(msgs)},
        )

        mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[i, False, SMTPException()] for i in range(len(msgs))],
        )

        msg_str_mock = mocker.MagicMock()
        msg_str_mock.create_str.return_value = "str_message"

        message_from_webhook_mock = mocker.patch(
            "chat.tasks.MessageFromWebhook",
            return_value=msg_str_mock,
        )

        results = send_manager(manager_id, "asd@.ru", manager_key)

        assert len(results) == 1
        assert results[0] == f"new_chat={msgs[0]['new_chat']};str_message"
        message_from_webhook_mock.assert_called_once_with(msgs[0])

    def test_fail_smtperrors_sending(self, mocker, correct_message_factory):
        manager_id = 11111
        manager_key = str(manager_id)

        msgs = [{
            "client_id": 333 + i,
            "topic": "AvotTAK:аноним",
            "prev_email": None,
            "new_chat": True,
        } for i in range(2)]

        mocker.patch(
            "chat.tasks.create_msgsdata_for_email",
            return_value={n: msg for n, msg in enumerate(msgs)},
        )

        mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[i, False, SMTPException()] for i in range(len(msgs))],
        )

        msg_str_mock = mocker.MagicMock()
        msg_str_mock.create_str.return_value = "str_message"

        message_from_webhook_mock = mocker.patch(
            "chat.tasks.MessageFromWebhook",
            return_value=msg_str_mock,
        )

        results = send_manager(manager_id, "asd@.ru", manager_key)

        assert len(results) == 2
        for i in range(len(results)):
            assert results[i] == f"new_chat={msgs[i]['new_chat']};str_message"
        assert message_from_webhook_mock.call_count == 2
