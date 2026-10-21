import pickle
import random
import string
from smtplib import SMTPException

import pytest
from celery.exceptions import Retry

import chat.tasks as tasks
from chat.tasks import choose_messages, send_manager, unpack_msgs, send_notification_task, notification_retry_task, \
    create_mail_id_task
from chat.tests.conftest import correct_message_factory
from chat.utils import MessageFromWebhook
from conftest import test_redis_broker


@pytest.fixture
def logger_off(mocker):
    return mocker.patch("chat.tasks.logger")


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
            message=input_message,
            proc_key: bool = False,
            same_msgs: bool = False,
    ) -> bytes:
        target_manager = str(manager_id)
        message["id"] = "".join(random.choice(string.ascii_letters) for _ in range(30)) if not same_msgs else message["id"]
        msg = MessageFromWebhook(message)

        msg_to_queue = pickle.dumps(msg.create())
        if proc_key:
            processing_key = f"{manager_id}:processing"
            broker.lpush(processing_key, msg_to_queue)
        else:
            broker.lpush(target_manager, msg_to_queue)
        return msg_to_queue

    return add_msg


@pytest.fixture
def precreate_ids_off(mocker):
    mocker.patch("chat.tasks.create_mail_id_task")


@pytest.mark.usefixtures("precreate_ids_off")
class TestSendManagerInt:
    def test_int_choose_messages(self, add_msg_for_manager, pd_redis_broker, mocker):
        manager_id = 11111
        manager_key = str(manager_id)
        processing_key = f"{manager_id}:processing"

        msg = {
            "client_id": 334,
            "topic": "AvotTAK:Аноним",
            "prev_email": None
        }
        create_msgsdata_mock = mocker.patch(
            "chat.tasks.load_and_extend_data_for_email",
            return_value={0: msg}
        )
        send_notifications_mock = mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[0, True]]
        )

        add_msg_for_manager(11111)
        messages, raw_messages = choose_messages(manager_key, processing_key)
        retries = send_manager(manager_id, "asd@.ru", messages)

        assert len(raw_messages) == 1
        assert len(retries) == 0

        create_msgsdata_mock.assert_called_once()
        send_notifications_mock.assert_called_once_with(
            "asd@.ru",
            emails_data=[(334, "AvotTAK:Аноним", None)],
            alias_keys=[0],
            view_result=True
        )


class TestChooseMessages:
    def test_one_message(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        manager_id = 11111
        manager_key = str(manager_id)
        processing_key = f"{manager_id}:processing"

        msg = correct_message_factory(item_id=True)
        add_msg_for_manager(manager_id, message=msg)
        msg_entity = MessageFromWebhook(msg).create()

        choose_result = choose_messages(manager_key, processing_key)
        messages, selected_raw = choose_result

        assert len(messages) == 1
        assert pd_redis_broker.llen(manager_key) == 0
        assert pd_redis_broker.llen(processing_key) == 1
        assert isinstance(messages, list)
        assert isinstance(messages[0], dict)
        assert isinstance(selected_raw, list)
        assert isinstance(selected_raw[0], bytes)

        for i in msg_entity:
            assert msg_entity[i] == messages[0].get(i)

    def test_add_wasted_msgs(self, add_msg_for_manager, pd_redis_broker):
        manager_id = 11111
        manager_key = str(manager_id)
        processing_key = f"{manager_id}:processing"

        add_msg_for_manager(manager_id)
        add_msg_for_manager(manager_id, proc_key=True)

        choose_result = choose_messages(manager_key, processing_key)
        messages, selected_raw = choose_result

        assert len(messages) == 2
        assert len(selected_raw) == 2
        assert pd_redis_broker.llen(processing_key) == 2

    def test_different_messages(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        manager_id  = 11111
        manager_key = str(manager_id)
        processing_key = f"{manager_id}:processing"

        msgs = []
        for i in range(5):
            msg = correct_message_factory(item_id=bool(i % 2))
            add_msg_for_manager(manager_key, msg)
            msgs.append(MessageFromWebhook(msg))

        messages, raw_messages = choose_messages(manager_key, processing_key)

        assert len(messages) == 5
        assert len(raw_messages) == 5
        assert pd_redis_broker.llen(manager_key) == 0
        assert pd_redis_broker.llen(processing_key) == 5

    def test_max_messages_from_one_chat(self, add_msg_for_manager, pd_redis_broker):
        manager_id = 11111
        manager_key = str(manager_id)
        processing_key = f"{manager_id}:processing"
        [add_msg_for_manager(manager_key) for _ in range(5)]

        messages, raw_messages = choose_messages(manager_key, processing_key)

        assert len(messages) == 2
        assert len(raw_messages) == 2
        assert pd_redis_broker.llen(manager_key) == 0
        assert pd_redis_broker.llen(processing_key) == 2

    def test_many_messages_from_different_chats(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        manager_id = 11111
        manager_key = str(manager_id)
        processing_key = f"{manager_id}:processing"

        for i in range(3):
            msg = correct_message_factory(item_id=bool(i % 2))
            add_msg_for_manager(manager_key, msg)
            for j in range(i):
                add_msg_for_manager(manager_key, msg)

        messages, raw_messages = choose_messages(manager_key, processing_key)

        assert len(messages) == 5
        assert len(raw_messages) == 5
        assert pd_redis_broker.llen(manager_key) == 0
        assert pd_redis_broker.llen(processing_key) == 5

    def test_max_emails_limit_respected_when_in_proc_pend_contains_same_chat_id(
            self,
            add_msg_for_manager,
            pd_redis_broker,
            correct_message_factory,
    ):
        manager_id = 11111
        chat_id = "MyChatId-123"
        manager_key = str(manager_id)
        processing_key = f"{manager_id}:processing"

        for i in range(3):
            msg = correct_message_factory(item_id=bool(i % 2))
            msg["chat_id"] = chat_id
            add_msg_for_manager(manager_key, msg)
            add_msg_for_manager(processing_key, msg)

        messages, raw_messages = choose_messages(manager_key, processing_key)

        assert len(messages) == 2
        assert len(raw_messages) == 2
        assert pd_redis_broker.llen(manager_key) == 0
        assert pd_redis_broker.llen(processing_key) == 2
        assert messages[0]["skipped_msgs"] == 4
        assert messages[1]["skipped_msgs"] == 0


@pytest.mark.usefixtures("precreate_ids_off")
class TestSendManager:
    def test_success_one_sending(self, mocker):
        manager_id = 11111

        msg = {
            "client_id": 334,
            "topic": "AvotTAK:Аноним",
            "prev_email": None
        }
        create_msgsdata_mock = mocker.patch(
            "chat.tasks.load_and_extend_data_for_email",
            return_value = {0: msg}
        )
        send_notifications_mock = mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[0, True]]
        )

        messages, raw_messages = [[msg], [b"msg_str"]]
        retries = send_manager(manager_id, "asd@.ru", messages)

        assert len(raw_messages) == 1
        assert len(retries) == 0

        create_msgsdata_mock.assert_called_once()
        send_notifications_mock.assert_called_once_with(
            "asd@.ru",
            emails_data=[(334, "AvotTAK:Аноним", None)],
            alias_keys=[0],
            view_result=True
        )

    def test_success_many_sending(self, mocker):
        manager_id = 11111

        msgs = [{
            "client_id": 334 + i,
            "topic": "AvotTAK:Аноним",
            "prev_email": None
        } for i in range(3)]

        mocker.patch(
            "chat.tasks.load_and_extend_data_for_email",
            return_value={n: msg for n, msg in enumerate(msgs)}
        )
        mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[i, True] for i in range(len(msgs))]
        )

        messages, raw_messages = [[dict()], [f"msg_str{i}".encode() for i in range(len(msgs))]]
        retries = send_manager(manager_id, "asd@.ru", messages)

        assert len(retries) == 0
        assert len(raw_messages) == 3

    def test_fail_one_unexpected_err_sending(self, mocker):
        manager_id = 11111

        msgs = [{
            "client_id": 333,
            "topic": "AvotTAK:Аноним",
            "prev_email": None
        }]

        mocker.patch(
            "chat.tasks.load_and_extend_data_for_email",
            return_value={n: msg for n, msg in enumerate(msgs)}
        )
        mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[i, False, RuntimeError()] for i in range(len(msgs))]
        )

        messages, raw_messages = [[dict()], [f"msg_str{i}".encode() for i in range(len(msgs))]]
        retries = send_manager(manager_id, "asd@.ru", messages)

        assert len(retries) == 0
        assert len(raw_messages) == 1

    def test_fail_smtperr_sending(self, mocker, correct_message_factory):
        manager_id = 11111

        msgs = [{
            "client_id": 333,
            "topic": "AvotTAK:Аноним",
            "prev_email": None,
        }]

        mocker.patch(
            "chat.tasks.load_and_extend_data_for_email",
            return_value={n: msg for n, msg in enumerate(msgs)},
        )

        mocker.patch(
            "chat.tasks.send_notifications_on_email",
            return_value=[[i, False, SMTPException()] for i in range(len(msgs))],
        )

        messages, raw_messages = [[dict()], [f"msg_str{i}".encode() for i in range(len(msgs))]]
        retries = send_manager(manager_id, "asd@.ru", messages)

        assert len(retries) == 1
        assert len(raw_messages) == 1
        assert retries[0] == pickle.dumps(msgs[0])


class TestUnpackMessages:
    def test_successful_unpack(self, add_msg_for_manager, correct_message_factory, pd_redis_broker):
        raw_msg = correct_message_factory()
        msg_entity = MessageFromWebhook(raw_msg)
        msg = msg_entity.create()

        add_msg_for_manager(11111, message=raw_msg, same_msgs=True)
        msgs = pd_redis_broker.lrange("11111", 0, -1)

        messages, remove_entity = unpack_msgs(msgs, 2)

        assert len(messages) == 1
        assert len(remove_entity) == 0
        message = messages.popitem()[1]
        assert message.get("skipped_msgs") == 0

        unpacked_msg =  message
        for i in msg:
            assert unpacked_msg[i] == msg[i]

    def test_under_limit(self, add_msg_for_manager, pd_redis_broker):
        _ = [add_msg_for_manager(11111) for _ in range(2)]
        msgs = pd_redis_broker.lrange("11111", 0, -1)

        messages, remove_entity = unpack_msgs(msgs, 2)
        assert isinstance(messages, dict)
        assert isinstance(remove_entity, list)
        assert len(messages) == 2
        assert [msgs.remove(i) for i in messages]
        assert not remove_entity
        assert not msgs
        for msg in messages:
            assert messages[msg]["skipped_msgs"] == 0

    def test_over_limit(self, add_msg_for_manager, pd_redis_broker):
        _ = [add_msg_for_manager(11111) for _ in range(5)]
        msgs = pd_redis_broker.lrange("11111", 0, -1)

        messages, remove_entity = unpack_msgs(msgs, 2)
        assert isinstance(messages, dict)
        assert len(messages) == 2
        assert [msgs.remove(i) for i in messages]
        assert [msgs.remove(i) for i in remove_entity]
        assert not msgs

        act_skipped = 0
        have_skipped = 0
        for msg in messages:
            skipped = messages[msg]["skipped_msgs"]
            if skipped != 0:
                have_skipped += 1
                act_skipped = skipped
                continue
            assert skipped == 0
        assert have_skipped == 1
        assert act_skipped == 3

    def test_already_read_msg(self, add_msg_for_manager, pd_redis_broker, correct_message_factory):
        msg = correct_message_factory(read=True)
        add_msg_for_manager(11111, message=msg)

        msgs = pd_redis_broker.lrange("11111", 0, -1)

        messages, remove_entity = unpack_msgs(msgs, 2)

        assert len(messages) == 1
        assert len(remove_entity) == 0


class TestSendNotifTask:
    def test_successful_send(self, add_msg_for_manager, pd_redis_broker, mocker, logger_off):
        manager = 11111
        add_msg_for_manager(11111, proc_key=True)
        mocker.patch("chat.tasks.send_manager", return_value=[])

        send_notification_task.run(manager, "asd@.ru")

        logger_off.info.assert_not_called()
        logger_off.error.assert_not_called()
        assert pd_redis_broker.lrange(f"{manager}", 0, -1) == []
        assert pd_redis_broker.lrange(f"{manager}:processing", 0, -1) == []
        assert pd_redis_broker.get(f"{manager}_lock") is None

    def test_failed_send(self, add_msg_for_manager, pd_redis_broker, mocker, logger_off):
        manager = 11111
        msg = add_msg_for_manager(11111, proc_key=True)
        mocker.patch("chat.tasks.send_manager", return_value=[msg])
        mocker.patch("chat.tasks.notification_retry_task")

        send_notification_task.run(manager, "asd@.ru")

        logger_off.info.assert_not_called()
        logger_off.error.assert_not_called()
        assert pd_redis_broker.lrange(f"{manager}", 0, -1) == []
        assert pd_redis_broker.lrange(f"{manager}:processing", 0, -1) == []
        assert pd_redis_broker.lrange(f"{manager}:retry", 0, -1) == [msg]
        assert pd_redis_broker.get(f"{manager}_lock") is None

    def test_messages_already_sent(self, mocker, logger_off):
        manager = 11111
        mocker.patch("chat.tasks.get_manager_messages", return_value=(0, 0))

        send_notification_task.run(manager, "asd@.ru")

        logger_off.info.assert_called_once_with(f"Messages for {manager} already sent")

    def test_lock_key_already_exists(self, pd_redis_broker, mocker, logger_off):
        manager = 11111

        mocker.patch("chat.tasks.get_manager_messages", return_value=(0, 1))
        mocker.patch("chat.tasks.RedisLocker.create_lock_key", return_value=None)

        with pytest.raises(Retry):
            send_notification_task.run(manager, "asd@.ru")
        logger_off.info.assert_called_once_with(f"Manager {manager} is locked, retrying later")


@pytest.mark.usefixtures("precreate_ids_off")
class TestNotifRetryTask:
    def test_successful_retry(self, add_msg_for_manager, pd_redis_broker, mocker, logger_off):
        manager = 11111
        manager_key = f"{manager}:retry"

        add_msg_for_manager(manager_key, proc_key=True)
        mocker.patch("chat.tasks.send_manager", return_value=[])

        notification_retry_task.run(manager, "asd@.ru")

        logger_off.info.assert_not_called()
        logger_off.error.assert_not_called()
        assert pd_redis_broker.lrange(manager_key, 0, -1) == []
        assert pd_redis_broker.lrange(f"{manager_key}:processing", 0, -1) == []
        assert pd_redis_broker.get(f"{manager_key}_lock") is None

    def test_failed_retry(self, add_msg_for_manager, pd_redis_broker, mocker, logger_off):
        manager = 11111
        manager_key = f"{manager}:retry"

        msg = add_msg_for_manager(manager_key, proc_key=True)
        mocker.patch("chat.tasks.send_manager", return_value=[msg])

        with pytest.raises(Retry):
            notification_retry_task.run(manager, "asd@.ru")

        logger_off.info.assert_not_called()
        logger_off.error.assert_not_called()
        assert pd_redis_broker.lrange(manager_key, 0, -1) == []
        assert pd_redis_broker.lrange(f"{manager_key}:processing", 0, -1) == [msg]
        assert pd_redis_broker.get(f"{manager_key}_lock") is None

    def test_retries_already_done(self, pd_redis_broker, logger_off):
        manager = 11111
        manager_key = f"{manager}:retry"

        notification_retry_task.run(manager, "asd@.ru")

        logger_off.info.assert_called_once_with(f"Retries for {manager_key} already done")

    def test_lock_key_already_exists(self, pd_redis_broker, mocker, logger_off):
        manager = 11111
        manager_key = f"{manager}:retry"

        mocker.patch("chat.tasks.get_manager_messages", return_value=(0, 1))
        mocker.patch("chat.tasks.RedisLocker.create_lock_key", return_value=None)

        with pytest.raises(Retry):
            notification_retry_task.run(manager, "asd@.ru")

        logger_off.info.assert_called_once_with(f"Manager {manager_key} is locked, retrying later")


class TestCreateMailIdsTask:
    def test_not_creating(self, pd_redis_broker):
        mails_key = "mails_ids"

        pd_redis_broker.lpush(mails_key, *[i for i in range(51)])
        create_mail_id_task.run()

        assert pd_redis_broker.llen(mails_key) == 51

    def test_creating_in_progress(self, pd_redis_broker, mocker, logger_off):
        mocker.patch("chat.tasks.RedisLocker.create_lock_key", return_value=None)

        create_mail_id_task.run()

        logger_off.info.assert_called_once_with(f"Creating mails id is running")

    def test_successful_creating(self, mocker, pd_redis_broker, logger_off):
        mocker.patch("chat.tasks.RedisLocker.create_lock_key", return_value=[b"lock", b"token"])
        mocker.patch("chat.tasks.RedisLocker.release_locking")

        class FakeFuture:
            def __init__(self, msg_id):
                self.msg_id = msg_id
            def result(self):
                return self.msg_id
            @staticmethod
            def exception():
                return None

        msg_ids = [f"msg-{i}" for i in range(100)]
        futures = [FakeFuture(msg_id) for msg_id in msg_ids]

        executor = mocker.MagicMock()
        executor.__enter__.return_value = executor
        executor.submit.side_effect = futures
        executor_context_mock = mocker.patch(
            "chat.tasks.concurrent.futures.ProcessPoolExecutor",
            return_value=executor,
        )
        mocker.patch(
            "chat.tasks.concurrent.futures.as_completed",
            return_value=futures,
        )

        create_mail_id_task.run()

        logger_off.error.assert_not_called()
        assert executor_context_mock.call_count == 1
        assert executor.submit.call_count == 100
        assert pd_redis_broker.llen("mails_ids") == 100

        actual_ids = pd_redis_broker.lrange("mails_ids", 0, -1)
        actual_ids = [item.decode() for item in actual_ids]
        assert set(actual_ids) == set(msg_ids)
