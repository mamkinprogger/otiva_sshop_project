from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock

import pytest


from chat.notifications.email_sending import (
    EmailNotification,
    EmailNotificationTypeError,
    EmailNotificationFieldError,
    EmailNotificationNoData, create_msgsdata_for_email, get_topic_and_prev_emails,
)
from chat.utils import MessageFieldsException

#переписать логгер офф, заменить на мэджик мог

@pytest.fixture
async def logger_off(mocker):
    mocker.patch("chat.notifications.email_sending.logger")

@pytest.fixture
def emails_data():
    return [
        (101, "topic-1", ["11.aa"]),
        (102, "topic-2", ["22.bb"]),
    ]


@pytest.fixture
def notification(emails_data):
    return EmailNotification(
        manager_email="manager@example.com",
        emails_data=emails_data,
    )

@pytest.fixture
def topic_new_client():
    pass

class TestEmailNotificationInit:
    def test_init_without_emails_data(self):
        notification = EmailNotification(manager_email="manager@example.com")

        assert notification.manager_email == "manager@example.com"
        assert notification.emails_data is None

    def test_init_with_emails_data(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic-1", ["11.aa"]),
            ],
        )

        assert notification.emails_data == {
            0: {
                "client_id": 101,
                "topic": "topic-1",
                "prev_emails": ["11.aa"],
                "alias_key": None,
            }
        }

    def test_init_with_alias_keys(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic-1", []),
                (102, "topic-2", []),
            ],
            alias_keys=["alias-1", "alias-2"],
        )

        assert notification.emails_data[0]["alias_key"] == "alias-1"
        assert notification.emails_data[1]["alias_key"] == "alias-2"

    def test_alias_keys_shorter_than_emails_data(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic-1", []),
                (102, "topic-2", []),
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
                [(101, "topic", [])],
                "not-a-list",
            )

    def test_create_emails_data_without_keys(self):
        notification = EmailNotification()
        notification._create_emails_data(
            [(101, "topic-1", ["a@example.com"]),(102, "topic-2", ["b@example.com"])],
            None
        )

        assert notification.emails_data == {
            0: {
                "client_id": 101,
                "topic": "topic-1",
                "prev_emails": ["a@example.com"],
                "alias_key": None,
            },
            1: {
                "client_id": 102,
                "topic": "topic-2",
                "prev_emails": ["b@example.com"],
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
                (101, "topic", []),
            ],
            alias_keys=["my-alias"],
        )

        notification.add_results_sending([(0, True, None)])
        assert notification.get_notifications_results() == [["my-alias", True]]

    def test_alias_key_is_used_for_failed_result(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic", []),
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

        assert notification.emails_data["sac.asd"]["prev_emails"] == ["22.bb", "sac.asd"]
        update_history.assert_called_once_with(102, ["22.bb", "sac.asd"])

    def test_failed_result_does_not_update_history(self, notification, mocker):
        update_history = mocker.patch("chat.notifications.email_sending.orm_update_client_emails_history")
        notification.emails_data["sac.asd"] = notification.emails_data.pop(1)
        notification.add_results_sending([("sac.asd", False, RuntimeError("A vot tak"))])
        notification.update_client_emails(("sac.asd", False))

        assert notification.emails_data["sac.asd"]["prev_emails"] == ["22.bb"]
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

class TestCreateEmailsList:
    @pytest.mark.parametrize("manager_email", [123, None])
    def test_manager_email_must_be_string(self, manager_email):
        notification = EmailNotification(
            manager_email=manager_email,
            emails_data=[
                (101, "topic", []),
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
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic", ["11.aa"]),
            ],
        )

        result = notification.create_emails_list()

        shop_email.assert_called_once_with("manager@example.com", "topic", "topic")
        shop_email.return_value.create_mail.assert_called_once_with(["11.aa"])
        assert result == [mail]
        assert notification.emails_data == {
            "<message-123@example.com>": {
                "client_id": 101,
                "topic": "topic",
                "prev_emails": ["11.aa"],
                "alias_key": None,
            }
        }

    def test_single_email_uses_alias(self):
        notification = EmailNotification(
            manager_email="manager@example.com",
            emails_data=[
                (101, "topic", []),
            ],
            alias_keys=["client-alias"],
        )

        result = notification.create_emails_list()

        assert isinstance(result, list)
        assert isinstance(result[0], MIMEMultipart)
        assert notification.emails_data[result[0]["Message-ID"]]["alias_key"] == "client-alias"

    def test_multiple_emails_are_created(self, notification, mocker):
        executor = mocker.patch("chat.notifications.email_sending.concurrent.futures.ProcessPoolExecutor")

        future_1 = mocker.Mock()
        future_1.exception.return_value = None
        future_1.result.return_value = {"Message-ID": "<message-1@example.com>"}

        future_2 = mocker.Mock()
        future_2.exception.return_value = None
        future_2.result.return_value = {"Message-ID": "<message-2@example.com>"}

        executor.return_value.__enter__.return_value.submit.side_effect = [
            future_1,
            future_2,
        ]

        result = notification.create_emails_list()

        assert result == [
            {"Message-ID": "<message-1@example.com>"},
            {"Message-ID": "<message-2@example.com>"},
        ]
        assert "<message-1@example.com>" in notification.emails_data
        assert "<message-2@example.com>" in notification.emails_data

        assert notification.emails_data["<message-1@example.com>"]["client_id"] == 101
        assert notification.emails_data["<message-2@example.com>"]["client_id"] == 102

    def test_failed_future_is_removed_and_logged(self, notification, mocker):
        executor = mocker.patch("chat.notifications.email_sending.concurrent.futures.ProcessPoolExecutor")
        logger = mocker.patch("chat.notifications.email_sending.logger")

        future_1 = mocker.Mock()
        future_1.exception.return_value = RuntimeError("boom")

        future_2 = mocker.Mock()
        future_2.exception.return_value = None
        future_2.result.return_value = {"Message-ID": "<message-2@example.com>"}

        executor.return_value.__enter__.return_value.submit.side_effect = [
            future_1,
            future_2,
        ]

        result = notification.create_emails_list()

        assert result == [{"Message-ID": "<message-2@example.com>"}]

        assert 0 not in notification.emails_data
        assert "<message-2@example.com>" in notification.emails_data
        logger.error.assert_called_once_with(repr(future_1.exception.return_value))


@pytest.mark.usefixtures("logger_off")
class TestCreateMsgsdataForEmail:
    def test_adds_topic_and_previous_emails_to_each_message(self, mocker):
        get_topic_and_prev_emails_mock = mocker.patch(
            "chat.notifications.email_sending.get_topic_and_prev_emails",
            side_effect=[
                (True, "Product-111", ["email1"]),
                (False, "НеОбъявление-222", ["email2", "email3"]),
            ],
        )

        msgs = [
            {
                "client_id": 10,
                "chat_id": "111",
                "call": "call-1",
                "new_chat": True,
                "item_id": 123,
            },
            {
                "client_id": 20,
                "chat_id": "222",
                "call": None,
                "new_chat": False,
                "item_id": None,
            },
        ]

        result = create_msgsdata_for_email(manager_id=999, msgs=msgs)

        assert result == {
            0: {
                "client_id": 10,
                "chat_id": "111",
                "call": "call-1",
                "new_chat": True,
                "item_id": 123,
                "topic": "Product-111",
                "prev_emails": ["email1"],
            },
            1: {
                "client_id": 20,
                "chat_id": "222",
                "call": None,
                "new_chat": False,
                "item_id": None,
                "topic": "НеОбъявление-222",
                "prev_emails": ["email2", "email3"],
            },
        }

        assert get_topic_and_prev_emails_mock.call_count == 2
        get_topic_and_prev_emails_mock.assert_any_call(999, 10, "111", "call-1", True, 123)
        get_topic_and_prev_emails_mock.assert_any_call(999, 20, "222", None, False, None)

    def test_fields_are_copied_from_input_messages(self, mocker):
        mocker.patch(
            "chat.notifications.email_sending.get_topic_and_prev_emails",
            return_value=(True, "Product-chat", []),
        )

        msgs = [
            {
                "client_id": 10,
                "chat_id": "chat",
                "call": "call",
                "new_chat": True,
                "item_id": 123,
                "subject": "Hello",
                "sender": "user@example.com",
            }
        ]

        result = create_msgsdata_for_email(manager_id=1, msgs=msgs)

        assert result[0]["subject"] == "Hello"
        assert result[0]["item_id"] == 123
        assert result[0]["sender"] == "user@example.com"
        assert result[0]["topic"] == "Product-chat"
        assert result[0]["prev_emails"] == []

    def test_missing_field_make_msg(self, mocker):
        mocker.patch(
            "chat.notifications.email_sending.get_topic_and_prev_emails",
            return_value=(True, "topic", []),
        )

        msgs = [{
            "client_id": 1,
            "chat_id": "chat",
            "call": None,
            "new_chat": False,
            }]

        with pytest.raises(MessageFieldsException):
            create_msgsdata_for_email(manager_id=1, msgs=msgs)

    def test_failed_message_is_removed(self, mocker):
        error = ValueError("val error")
        mocker.patch(
            "chat.notifications.email_sending.get_topic_and_prev_emails",
            side_effect=error,
        )

        msgs = [
            {
                "client_id": 1,
                "chat_id": "chat",
                "call": None,
                "new_chat": False,
                "item_id": None,
            }
        ]

        result = create_msgsdata_for_email(manager_id=1, msgs=msgs)
        assert result == {}

    def test_failed_message_does_not_affect_other_messages(self, mocker):
        error = ValueError("database error")

        mocker.patch(
            "chat.notifications.email_sending.get_topic_and_prev_emails",
            side_effect=[
                error,
                (True, "Product-222", ["email@example.com"]),
            ],
        )

        msgs = [
            {
                "client_id": 1,
                "chat_id": "chat-111",
                "call": None,
                "new_chat": False,
                "item_id": None,
            },
            {
                "client_id": 2,
                "chat_id": "chat-222",
                "call": "call",
                "new_chat": True,
                "item_id": 456,
            },
        ]

        result = create_msgsdata_for_email(manager_id=1, msgs=msgs)

        assert result == {
            1: {
                "client_id": 2,
                "chat_id": "chat-222",
                "call": "call",
                "new_chat": True,
                "item_id": 456,
                "topic": "Product-222",
                "prev_emails": ["email@example.com"],
            }
        }

    def test_empty_messages_returns_empty_dict(self, mocker):
        get_topic_and_prev_emails_mock = mocker.patch("chat.notifications.email_sending.get_topic_and_prev_emails")

        result = create_msgsdata_for_email(
            manager_id=1,
            msgs=[],
        )

        assert result == {}
        get_topic_and_prev_emails_mock.assert_not_called()


class TestGetTopicAndPrevEmails:
    def test_without_item_id_uses_default_product(self, mocker):
        orm_update_manager_load = mocker.patch(
            "chat.notifications.email_sending.orm_update_manager_load",
            return_value=(True, ["email1", "email2"]),
        )
        orm_get_avito_product = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")

        result = get_topic_and_prev_emails(
            manager_id=10,
            client_id=20,
            chat_id="chat-123",
            call="call",
            new_chat=True,
            item_id=None,
        )

        assert result == (True, "НеОбъявление-chat-123", ["email1", "email2"])

        orm_update_manager_load.assert_called_once_with(10, 20, "chat-123", "call", True)
        orm_get_avito_product.assert_not_called()

    def test_with_item_id_uses_avito_product(self, mocker):
        orm_update_manager_load = mocker.patch(
            "chat.notifications.email_sending.orm_update_manager_load",
            return_value=(False, ["previous@example.com"]),
        )
        orm_get_avito_product = mocker.patch(
            "chat.notifications.email_sending.orm_get_avito_product",
            return_value="iPhone 15",
        )

        result = get_topic_and_prev_emails(
            manager_id=1,
            client_id=2,
            chat_id="abc",
            call=None,
            new_chat=False,
            item_id=12345,
        )

        assert result == (False, "iPhone 15-abc", ["previous@example.com"])

        orm_update_manager_load.assert_called_once_with(1, 2, "abc", None, False)
        orm_get_avito_product.assert_called_once_with(12345)

    def test_falsy_item_id_does_not_query_product(self, mocker):
        mocker.patch(
            "chat.notifications.email_sending.orm_update_manager_load",
            return_value=(True, []),
        )
        orm_get_avito_product = mocker.patch("chat.notifications.email_sending.orm_get_avito_product")

        result = get_topic_and_prev_emails(
            manager_id=1,
            client_id=2,
            chat_id="chat",
            call=None,
            new_chat=False,
            item_id=None,
        )

        assert result[1] == "НеОбъявление-chat"
        orm_get_avito_product.assert_not_called()

    def test_update_manager_load_result_is_returned(self, mocker):
        mocker.patch(
            "chat.notifications.email_sending.orm_update_manager_load",
            return_value=(False, ["a", "b", "c"]),
        )
        mocker.patch(
            "chat.notifications.email_sending.orm_get_avito_product",
            return_value="Product",
        )

        result = get_topic_and_prev_emails(
            manager_id=100,
            client_id=200,
            chat_id="chat-id",
            call="some-call",
            new_chat=True,
            item_id=999,
        )

        just_added, topic, previous_emails = result

        assert just_added is False
        assert topic == "Product-chat-id"
        assert previous_emails == ["a", "b", "c"]
