from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid

import pytest

import chat.notifications.email_sending as email_sending
from chat.notifications.email_sending import (
    EmailNotification,
    EmailNotificationTypeError,
    EmailNotificationFieldError,
    EmailNotificationNoData, load_and_extend_data_for_email, load_fields_to_send_on_email, EmailNotificationError
)
from chat.utils import MessageFieldsException
from users.models import ClientPermissionError


@pytest.fixture
async def logger_off(mocker):
    turn_off = mocker.patch("chat.notifications.email_sending.logger")
    return turn_off


@pytest.fixture
def pd_redis_broker(monkeypatch, test_redis_broker):
    monkeypatch.setattr(
        email_sending,
        "redis_broker",
        test_redis_broker,
    )
    return test_redis_broker


@pytest.fixture
def pd_sredis(monkeypatch, test_sredis):
    monkeypatch.setattr(
        email_sending,
        "sredis",
        test_sredis,
    )
    return test_sredis


@pytest.fixture
def emails_data():
    return [
        (101, "topic-1", "11.aa"),
        (102, "topic-2", "22.bb"),
    ]


@pytest.fixture
def notification(emails_data):
    return EmailNotification(
        manager_email="manager@example.com",
        emails_data=emails_data,
    )


class TestEmailNotificationInit:
    def test_init_without_emails_data(self):
        notification = EmailNotification(manager_email="manager@example.com")

        assert notification.manager_email == "manager@example.com"
        assert notification.emails_data is None

    def test_init_with_emails_data(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic-1", "11.aa"),
            ],
        )

        assert notification.emails_data == {
            0: {
                "client_id": 101,
                "topic": "topic-1",
                "prev_email": "11.aa",
                "alias_key": None,
            }
        }

    def test_init_with_alias_keys(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic-1", None),
                (102, "topic-2", None),
            ],
            alias_keys=["alias-1", "alias-2"],
        )

        assert notification.emails_data[0]["alias_key"] == "alias-1"
        assert notification.emails_data[1]["alias_key"] == "alias-2"

    def test_alias_keys_shorter_than_emails_data(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic-1", None),
                (102, "topic-2", None),
            ],
            alias_keys=["alias-1"],
        )

        assert notification.emails_data[0]["alias_key"] == "alias-1"
        assert notification.emails_data[1]["alias_key"] is None


class TestCreateEmailsData:
    def test_emails_data_must_be_list(self):
        notification = EmailNotification()

        with pytest.raises(EmailNotificationTypeError, match="Emails_data must be a list"):
            notification._create_emails_data(
                ("not", "a", "list"),
                [],
            )

    def test_keys_must_be_list(self):
        notification = EmailNotification()

        with pytest.raises(EmailNotificationTypeError, match="keys must be a list"):
            notification._create_emails_data(
                [(101, "topic", None)],
                "not-a-list",
            )

    def test_create_emails_data_without_keys(self):
        notification = EmailNotification()
        notification._create_emails_data(
            [(101, "topic-1", "a@example.com"),(102, "topic-2", "b@example.com")],
            None
        )

        assert notification.emails_data == {
            0: {
                "client_id": 101,
                "topic": "topic-1",
                "prev_email": "a@example.com",
                "alias_key": None,
            },
            1: {
                "client_id": 102,
                "topic": "topic-2",
                "prev_email": "b@example.com",
                "alias_key": None,
            },
        }

class TestAddResultsSending:
    def test_add_success_result(self, notification):
        notification.add_results_sending([(0, True, None)])

        assert notification.emails_data[0]["success"] is True
        assert "fail_reason" not in notification.emails_data[0]

    def test_add_failed_result(self, notification):
        notification.add_results_sending([(0, False, "SMTP error")])

        assert notification.emails_data[0]["success"] is False
        assert notification.emails_data[0]["fail_reason"] == "SMTP error"

    def test_add_multiple_results(self, notification):
        notification.add_results_sending([
            (0, True, None),
            (1, False, "Connection error"),
        ])

        assert notification.emails_data[0]["success"] is True
        assert notification.emails_data[1]["success"] is False
        assert notification.emails_data[1]["fail_reason"] == "Connection error"


class TestGetNotificationsResults:
    def test_results_without_aliases(self, notification):
        result = notification.get_notifications_results()
        assert result == [[0, None], [1, None]]

    def test_success_results(self, notification):
        notification.add_results_sending([(0, True, None), (1, True, None)])
        result = notification.get_notifications_results()
        assert result == [[0, True],[1, True]]

    def test_failed_results_include_reason(self, notification):
        notification.add_results_sending([(0, False, "SMTP error"), (1, True, None)])
        result = notification.get_notifications_results()
        assert result == [[0, False, "SMTP error"], [1, True]]

    def test_alias_key_is_used_in_result(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic", None),
            ],
            alias_keys=["my-alias"],
        )

        notification.add_results_sending([(0, True, None)])
        assert notification.get_notifications_results() == [["my-alias", True]]

    def test_alias_key_is_used_for_failed_result(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic", None),
            ],
            alias_keys=["my-alias"],
        )

        notification.add_results_sending([(0, False, "some error")])
        assert notification.get_notifications_results() == [["my-alias", False, "some error"]]


class TestUpdateClientEmails:
    def test_success_updates_previous_emails(self, notification, mocker):
        update_history = mocker.patch("chat.notifications.email_sending.orm_update_client_emails_history")
        notification.emails_data["sac.asd"] = notification.emails_data.pop(1)
        notification.add_results_sending([("sac.asd", True, None)])
        notification.update_client_emails(("sac.asd", True))

        assert notification.emails_data["sac.asd"]["prev_email"] == "sac.asd"
        update_history.assert_called_once_with(102, "sac.asd")

    def test_failed_result_does_not_update_history(self, notification, mocker):
        update_history = mocker.patch("chat.notifications.email_sending.orm_update_client_emails_history")
        notification.emails_data["sac.asd"] = notification.emails_data.pop(1)
        notification.add_results_sending([("sac.asd", False, RuntimeError("A vot tak"))])
        notification.update_client_emails(("sac.asd", False))

        assert notification.emails_data["sac.asd"]["prev_email"] == "22.bb"
        update_history.assert_not_called()

    def test_unknown_email_id_raises_custom_error(self, notification):
        with pytest.raises(EmailNotificationFieldError, match="Not Notification aaa in self.emails_data"):
            notification.update_client_emails(("aaa", True))

    def test_original_key_error_is_preserved(self, notification):
        with pytest.raises(EmailNotificationFieldError) as exc_info:
            notification.update_client_emails(("bbb", True))
        assert isinstance(exc_info.value.__cause__, KeyError)


class TestUpdateClientsEmails:
    def test_single_result_calls_update_directly(self, notification, mocker):
        update = mocker.patch.object(
            notification,
            "update_client_emails",
        )
        notification.update_clients_emails([("aaa", True)])
        update.assert_called_once_with(("aaa", True))

    def test_success_updates_previous_emails_for_one_client(self, mocker):
        emails_data = [(101, "topic-1", "11.aa"), (101, "topic-1", "00.aa")]
        notification = EmailNotification(manager_email="amanager@u.ru", emails_data=emails_data)

        notification.emails_data["sac.asd"] = notification.emails_data.pop(0)
        notification.emails_data["sac.asd.second"] = notification.emails_data.pop(1)
        notification.add_results_sending([("sac.asd", True, None), ("sac.asd.second", True, None)])
        update_history = mocker.patch("chat.notifications.email_sending.orm_update_client_emails_history")

        notification.update_clients_emails([("sac.asd", True), ("sac.asd.second", True)])

        assert notification.emails_data["sac.asd"]["prev_email"] == "sac.asd"
        assert notification.emails_data["sac.asd.second"]["prev_email"] == "sac.asd.second"
        update_history.assert_called_once_with(101, "sac.asd.second")

    def test_success_updates_previous_emails_for_many_client(self, notification, mocker):
        notification.emails_data["sac.asd"] = notification.emails_data.pop(0)
        notification.emails_data["sac.asd.second"] = notification.emails_data.pop(1)
        notification.add_results_sending([("sac.asd", True, None), ("sac.asd.second", True, None)])
        update_history = mocker.patch("chat.notifications.email_sending.orm_update_client_emails_history")

        notification.update_clients_emails([("sac.asd", True), ("sac.asd.second", True)])

        assert notification.emails_data["sac.asd"]["prev_email"] == "sac.asd"
        assert notification.emails_data["sac.asd.second"]["prev_email"] == "sac.asd.second"
        for i in ([101, "sac.asd"], [102, "sac.asd.second"]):
            update_history.assert_any_call(*i)

    def test_failed_results_ignored(self, mocker):
        emails_data = [(101, "topic-1", "11.aa"), (101, "topic-1", "00.aa")]
        notification = EmailNotification(manager_email="amanager@u.ru", emails_data=emails_data)

        notification.emails_data["sac.asd"] = notification.emails_data.pop(0)
        notification.emails_data["sac.asd.second"] = notification.emails_data.pop(1)
        notification.add_results_sending([("sac.asd", True, None), ("sac.asd.second", False, RuntimeError("A vot tak"))])
        update_history = mocker.patch("chat.notifications.email_sending.orm_update_client_emails_history")

        notification.update_clients_emails([("sac.asd", True), ("sac.asd.second", False)])

        assert notification.emails_data["sac.asd"]["prev_email"] == "sac.asd"
        assert notification.emails_data["sac.asd.second"]["prev_email"] == "00.aa"
        update_history.assert_called_once_with(101, "sac.asd")

@pytest.mark.usefixtures("pd_redis_broker")
class TestCreateEmailsList:
    @pytest.mark.parametrize("manager_email", [123, None])
    def test_manager_email_must_be_string(self, manager_email):
        notification = EmailNotification(
            manager_email=manager_email,
            emails_data=[
                (101, "topic", None),
            ],
        )
        with pytest.raises(EmailNotificationTypeError, match="Manager_email must be a string"):
            notification.create_emails_list()

    @pytest.mark.parametrize("emails_data", [None, {}, tuple()])
    def test_emails_data_is_required(self, emails_data):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=emails_data,
        )
        with pytest.raises(EmailNotificationNoData, match="Emails_data must be passed"):
            notification.create_emails_list()


    def test_single_email_is_created(self, mocker):
        shop_email = mocker.patch("chat.notifications.email_sending.ShopEmail")
        mail = {"Message-ID": "<message-123@example.com>"}
        shop_email.return_value.create_mail.return_value = mail
        redis_broker_mock = mocker.patch("chat.notifications.email_sending.redis_broker")
        redis_broker_mock.rpop.return_value = None

        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic", "11.aa"),
            ],
        )

        result = notification.create_emails_list()

        shop_email.assert_called_once_with("manager@example.com", "topic", "topic")
        redis_broker_mock.rpop.assert_called_once()
        shop_email.return_value.create_mail.assert_called_once_with(["11.aa"], None)
        assert result == [mail]
        assert notification.emails_data == {
            "<message-123@example.com>": {
                "client_id": 101,
                "topic": "topic",
                "prev_email": "11.aa",
                "alias_key": None,
            }
        }

    def test_single_email_uses_alias(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic", None),
            ],
            alias_keys=["client-alias"],
        )

        result = notification.create_emails_list()

        assert isinstance(result, list)
        assert isinstance(result[0], MIMEMultipart)
        assert notification.emails_data[result[0]["Message-ID"]]["alias_key"] == "client-alias"

    @pytest.mark.slow
    def test_multiple_emails_are_created(self, notification, pd_redis_broker, mocker):
        mail_id1 = make_msgid()
        mail_id2 = make_msgid()

        pd_redis_broker.lpush("mails_ids", mail_id1, mail_id2)

        shop_email = mocker.patch("chat.notifications.email_sending.ShopEmail")
        mail1 = {"Message-ID": mail_id1}
        mail2 = {"Message-ID": mail_id2}
        shop_email.return_value.create_mail.side_effect = [
            mail1,
            mail2,
        ]

        result = notification.create_emails_list()

        assert pd_redis_broker.llen("mails_ids") == 0
        assert result == [mail1, mail2]
        assert notification.emails_data == {
            mail_id1: {
                "client_id": 101,
                "topic": "topic-1",
                "prev_email": "11.aa",
                "alias_key": None,
            },
            mail_id2: {
                "client_id": 102,
                "topic": "topic-2",
                "prev_email": "22.bb",
                "alias_key": None,
            },
        }

    @pytest.mark.slow
    def test_failed_mail_is_removed_and_logged(self, notification, pd_redis_broker, mocker):
        mail_id = make_msgid()
        pd_redis_broker.lpush("mails_ids", "wasted_id", mail_id)

        shop_email = mocker.patch("chat.notifications.email_sending.ShopEmail")
        mail = {"Message-ID": mail_id}
        shop_email.return_value.create_mail.side_effect = [
            RuntimeError("AonoNeTak"),
            mail,
        ]
        logger = mocker.patch("chat.notifications.email_sending.logger")

        result = notification.create_emails_list()

        assert pd_redis_broker.llen("mails_ids") == 0
        assert result == [mail]
        assert 0 not in notification.emails_data
        assert mail_id in notification.emails_data
        logger.error.assert_called_once()


class TestLoadFieldsToSendOnEmail:
    def test_without_item_id_uses_default_product(self, mocker, pd_sredis):
        client_data = {
            "client_added": True,
            "client_name": "Аноним",
            "prev_email": "email2",
            "chat_added": True,
            "increase_manager_load": True,
            }

        orm_get_or_create_client_from_his_msg = mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value=client_data
        )
        update_manager_load_mock = mocker.patch("chat.notifications.email_sending.update_manager_load")
        orm_get_avito_product = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")

        result = load_fields_to_send_on_email(
            manager_id=10,
            client_id=20,
            chat_id="chat-123",
            call="call",
            item_id=None,
        )

        assert result == ("НеОбъявление-chat-123:Аноним", client_data["prev_email"])

        orm_get_or_create_client_from_his_msg.assert_called_once_with(10, 20, "chat-123", 0)
        update_manager_load_mock.assert_called_once_with(10, "call", True)
        orm_get_avito_product.assert_not_called()

    def test_with_item_id_uses_avito_product(self, mocker, pd_sredis):
        client_data = {
            "client_added": False,
            "client_name": "Аноним",
            "prev_email": "previous@example.com",
            "chat_added": False,
            "increase_manager_load": False,
        }

        orm_get_or_create_client_from_his_msg = mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value=client_data
        )
        update_manager_load_mock = mocker.patch("chat.notifications.email_sending.update_manager_load")
        orm_get_avito_product = mocker.patch(
            "chat.notifications.email_sending.orm_get_avito_product",
            return_value="iPhone 15",
        )

        result = load_fields_to_send_on_email(
            manager_id=1,
            client_id=2,
            chat_id="abc",
            call=None,
            item_id=12345,
        )

        assert result == ("iPhone 15-abc:Аноним", "previous@example.com")

        orm_get_or_create_client_from_his_msg.assert_called_once_with(1, 2, "abc", 0)
        update_manager_load_mock.assert_called_once_with(1, None, False)
        orm_get_avito_product.assert_called_once_with(12345)

    def test_falsy_item_id_does_not_query_product(self, mocker, pd_sredis):
        client_data = {
            "client_added": False,
            "client_name": "Аноним",
            "prev_email": "previous@example.com",
            "chat_added": False,
            "increase_manager_load": False,
        }

        mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value=client_data
        )
        update_manager_load_mock = mocker.patch("chat.notifications.email_sending.update_manager_load")
        orm_get_avito_product = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")

        result = load_fields_to_send_on_email(
            manager_id=1,
            client_id=2,
            chat_id="chat",
            call=None,
            item_id=None,
        )

        assert result[0] == "НеОбъявление-chat:Аноним"
        orm_get_avito_product.assert_not_called()
        update_manager_load_mock.assert_called_once_with(1, None, False)

    def test_update_manager_load_result_is_returned(self, mocker, pd_sredis):
        mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value={
                "client_added": False,
                "client_name": "Аноним",
                "prev_email": "c",
                "chat_added": True,
                "increase_manager_load": False,
            },
        )
        update_manager_load_mock = mocker.patch("chat.notifications.email_sending.update_manager_load")
        mocker.patch(
            "chat.notifications.email_sending.orm_get_avito_product",
            return_value="Product",
        )

        result = load_fields_to_send_on_email(
            manager_id=100,
            client_id=200,
            chat_id="chat-id",
            call="some-call",
            item_id=999,
        )

        topic, previous_email = result

        assert topic == "Product-chat-id:Аноним"
        assert previous_email == "c"
        update_manager_load_mock.assert_called_once_with(100, "some-call", False)

    def test_chat_already_added_previous_worker(self, mocker, pd_sredis):
        mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value={
                "client_added": False,
                "client_name": "Аноним",
                "prev_email": "c",
                "chat_added": False,
                "increase_manager_load": False,
            },
        )
        update_manager_load_mock = mocker.patch("chat.notifications.email_sending.update_manager_load")
        mocker.patch(
            "chat.notifications.email_sending.orm_get_avito_product",
            return_value="Product",
        )

        result = load_fields_to_send_on_email(
            manager_id=100,
            client_id=200,
            chat_id="chat-id",
            call="some-call",
            item_id=999,
        )

        topic, previous_email = result

        assert topic == "Product-chat-id:Аноним"
        assert previous_email == "c"
        update_manager_load_mock.assert_called_once_with(100, "some-call", False)

    def test_message_already_read(self, mocker, pd_sredis):
        mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value={
                "client_added": False,
                "client_name": "Аноним",
                "prev_email": "c",
                "chat_added": True,
                "increase_manager_load": False,
            },
        )
        orm_get_avito_product_mock = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")
        update_manager_load_mock = mocker.patch("chat.notifications.email_sending.update_manager_load")

        with pytest.raises(EmailNotificationError, match="already read"):
            load_fields_to_send_on_email(
                manager_id=100,
                client_id=200,
                chat_id="chat-id",
                call="some-call",
                item_id=999,
                read=1,
            )

        update_manager_load_mock.assert_called_once_with(100, "some-call", False)
        orm_get_avito_product_mock.assert_not_called()

    def test_increase_manager_load(self, mocker, pd_sredis):
        mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value={
                "client_added": True,
                "client_name": "Аноним",
                "prev_email": "c",
                "chat_added": True,
                "increase_manager_load": True,
            },
        )
        orm_get_avito_product_mock = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")
        orm_update_manager_load_mock = mocker.patch("chat.notifications.email_sending.orm_update_manager_load")

        load_fields_to_send_on_email(
            manager_id=100,
            client_id=200,
            chat_id="chat-id",
            call="some-call",
            item_id=999,
        )
        orm_update_manager_load_mock.assert_called_once_with(100, "some-call", True)
        orm_get_avito_product_mock.assert_called_once()
        assert pd_sredis.hget("managers", 100) == b'1'

    def test_increase_manger_load_despite_read(self, mocker, pd_sredis):
        mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            return_value={
                "client_added": True,
                "client_name": "Аноним",
                "prev_email": "c",
                "chat_added": False,
                "increase_manager_load": True,
            },
        )
        orm_get_avito_product_mock = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")
        orm_update_manager_load_mock = mocker.patch("chat.notifications.email_sending.orm_update_manager_load")

        with pytest.raises(EmailNotificationError, match="already read"):
            load_fields_to_send_on_email(
                manager_id=100,
                client_id=200,
                chat_id="chat-id",
                call="some-call",
                item_id=999,
                read=1,
            )

        orm_update_manager_load_mock.assert_called_once_with(100, "some-call", True)
        orm_get_avito_product_mock.assert_not_called()


    def test_permission_error(self, mocker, pd_sredis, logger_off):
        mocker.patch(
            "chat.notifications.email_sending.orm_get_or_create_client_from_his_msg",
            side_effect=ClientPermissionError("А нельзя"),
        )
        orm_get_avito_product_mock = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")
        update_manager_load_mock = mocker.patch("chat.notifications.email_sending.update_manager_load")

        with pytest.raises(EmailNotificationError, match="^$"):
            load_fields_to_send_on_email(
                manager_id=100,
                client_id=200,
                chat_id="chat-id",
                call="some-call",
                item_id=999,
                read=1,
            )

        update_manager_load_mock.assert_not_called()
        orm_get_avito_product_mock.assert_not_called()
        logger_off.warning.assert_called_once_with(repr(ClientPermissionError("А нельзя")))


@pytest.mark.usefixtures("logger_off")
class TestLoadAndExtendDataForEmail:
    def test_adds_topic_and_previous_emails_to_each_message(self, mocker):
        load_fields_to_send_on_email_mock = mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            side_effect=[
                ("Product-111", "email1"),
                ("НеОбъявление-222", "email3"),
            ],
        )

        msgs = [
            {
                "client_id": 10,
                "chat_id": "111",
                "call": "call-1",
                "item_id": 123,
                "read": None,
                "skipped_msgs": 0,
            },
            {
                "client_id": 20,
                "chat_id": "222",
                "call": None,
                "item_id": None,
                "read": None,
                "skipped_msgs": 0,
            },
        ]

        result = load_and_extend_data_for_email(manager_id=999, msgs=msgs)

        assert result == {
            0: {
                "client_id": 10,
                "chat_id": "111",
                "call": "call-1",
                "item_id": 123,
                "topic": "Product-111",
                "prev_email": "email1",
                "read": None,
                "skipped_msgs": 0,
            },
            1: {
                "client_id": 20,
                "chat_id": "222",
                "call": None,
                "item_id": None,
                "topic": "НеОбъявление-222",
                "prev_email": "email3",
                "read": None,
                "skipped_msgs": 0,
            },
        }

        assert load_fields_to_send_on_email_mock.call_count == 2
        load_fields_to_send_on_email_mock.assert_any_call(999, 10, "111", "call-1", 123, None, 0)
        load_fields_to_send_on_email_mock.assert_any_call(999, 20, "222", None, None, None, 0)

    def test_fields_are_copied_from_input_messages(self, mocker):
        mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            return_value=("Product-chat", None),
        )

        msgs = [
            {
                "client_id": 10,
                "chat_id": "chat",
                "call": "call",
                "item_id": 123,
                "subject": "Hello",
                "sender": "user@example.com",
                "read": None,
                "skipped_msgs": 0,
            }
        ]

        result = load_and_extend_data_for_email(manager_id=1, msgs=msgs)

        assert result[0]["subject"] == "Hello"
        assert result[0]["item_id"] == 123
        assert result[0]["sender"] == "user@example.com"
        assert result[0]["topic"] == "Product-chat"
        assert result[0]["prev_email"] is None

    def test_missing_field_make_msg(self, mocker):
        mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            return_value=("topic", None),
        )

        msgs = [{
            "client_id": 1,
            "chat_id": "chat",
            "call": None,
            "read": None,
            "skipped_msgs": 0,
            }]

        with pytest.raises(MessageFieldsException):
            load_and_extend_data_for_email(manager_id=1, msgs=msgs)

    def test_failed_message_is_removed(self, mocker, logger_off):
        error = ValueError("val error")
        mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            side_effect=error,
        )

        msgs = [
            {
                "client_id": 1,
                "chat_id": "chat",
                "call": None,
                "item_id": None,
                "read": None,
                "skipped_msgs": 0,
            }
        ]

        result = load_and_extend_data_for_email(manager_id=1, msgs=msgs)
        assert result == {}
        logger_off.error.assert_called_once_with(repr(error))

    def test_read_message_is_removed(self, mocker, logger_off):
        error = EmailNotificationError("Already read")
        mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            side_effect=error,
        )

        msgs = [
            {
                "client_id": 1,
                "chat_id": "chat",
                "call": None,
                "item_id": None,
                "read": None,
                "skipped_msgs": 0,
            }
        ]

        result = load_and_extend_data_for_email(manager_id=1, msgs=msgs)
        assert result == {}
        logger_off.error.assert_not_called()

    def test_failed_message_does_not_affect_other_messages(self, mocker, logger_off):
        error = ValueError("database error")

        mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            side_effect=[
                error,
                ("Product-222", "email@example.com"),
            ],
        )

        msgs = [
            {
                "client_id": 1,
                "chat_id": "chat-111",
                "call": None,
                "item_id": None,
                "read": None,
                "skipped_msgs": 0,
            },
            {
                "client_id": 2,
                "chat_id": "chat-222",
                "call": "call",
                "item_id": 456,
                "read": None,
                "skipped_msgs": 0,
            },
        ]

        result = load_and_extend_data_for_email(manager_id=1, msgs=msgs)

        assert result == {
            1: {
                "client_id": 2,
                "chat_id": "chat-222",
                "call": "call",
                "item_id": 456,
                "topic": "Product-222",
                "prev_email": "email@example.com",
                "read": None,
                "skipped_msgs": 0,
            }
        }
        logger_off.error.assert_called_once_with(repr(error))

    def test_emailerror_cause_permission_error(self, mocker, logger_off):
        error = EmailNotificationError()
        mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            side_effect=error,
        )

        msgs = [
            {
                "client_id": 1,
                "chat_id": "chat",
                "call": None,
                "item_id": None,
                "read": None,
                "skipped_msgs": 0,
            }
        ]

        result = load_and_extend_data_for_email(manager_id=1, msgs=msgs)
        assert result == {}
        logger_off.error.assert_not_called()

    def test_empty_messages_returns_empty_dict(self, mocker):
        load_fields_to_send_on_email_mock = mocker.patch("chat.notifications.email_sending.load_fields_to_send_on_email")

        result = load_and_extend_data_for_email(
            manager_id=1,
            msgs=[],
        )

        assert result == {}
        load_fields_to_send_on_email_mock.assert_not_called()

    def test_prev_worker_already_create_chat(self, mocker):
        mocker.patch(
            "chat.notifications.email_sending.load_fields_to_send_on_email",
            return_value=("Product-222", "email2"),
        )

        msgs = [
            {
                "client_id": 1,
                "chat_id": "chat",
                "call": None,
                "item_id": 456,
                "read": None,
                "skipped_msgs": 0,
            }
        ]

        result = load_and_extend_data_for_email(manager_id=1, msgs=msgs)
        assert result == {
            0: {
                "client_id": 1,
                "chat_id": "chat",
                "call": None,
                "item_id": 456,
                "topic": "Product-222",
                "prev_email": "email2",
                "read": None,
                "skipped_msgs": 0,
            }
        }

