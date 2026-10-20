import logging
import smtplib
from email.mime.multipart import MIMEMultipart

import pytest

from chat.utils import MessageFromWebhook, MessageFieldsException, CreateMailException, ShopEmail, \
    InvalidMailFieldException, SMTPEmailSender


@pytest.fixture
def shop_email():
    return ShopEmail(
        to_email="recipient@example.com",
        subject="Hello",
        text="Test message",
    )

@pytest.fixture
async def logger_off(mocker):
    turned_off = mocker.patch("chat.utils.logger")
    return turned_off


class TestMessageFromWebhook:
    def test_create_message_data_for_manager(self, correct_message_factory):
        res = MessageFromWebhook(correct_message_factory(with_call=True, item_id=True)).create()
        assert isinstance(res, dict)
        assert isinstance(res.get("client_id"), int)
        assert isinstance(res.get("chat_id"), str)
        assert isinstance(res.get("sending_time"), int)
        assert isinstance(res.get("call"), str)
        assert isinstance(res.get("item_id"), int)
        assert res.get("read") is None

        str_res = MessageFromWebhook(correct_message_factory(with_call=True, item_id=True)).create_str()
        assert isinstance(str_res, str)

    def test_create_message_data_for_manager_without_call(self, correct_message_factory):
        res_list = [
            MessageFromWebhook(correct_message_factory(with_call=False)).create(),
            MessageFromWebhook(correct_message_factory(with_call=False, item_id=False)).create(),
        ]
        for i in res_list:
            assert isinstance(i, dict)
            assert i.get("call") is None

    def test_create_message_data_for_manager_without_item_id(self, correct_message_factory):
        res_list = [
            MessageFromWebhook(correct_message_factory(item_id=False)).create(),
            MessageFromWebhook(correct_message_factory(item_id=False, with_call=False)).create(),
        ]
        for i in res_list:
            assert i.get("item_id") is None

    def test_create_message_data_for_manager_without_text(self, correct_message_factory):
        res_list = [
            MessageFromWebhook(correct_message_factory(text=False)).create(),
            MessageFromWebhook(correct_message_factory(text=False, item_id=False,)).create(),
            MessageFromWebhook(correct_message_factory(text=False, item_id=False, with_call=False)).create(),
        ]
        for i in res_list:
            assert i.get("text") is None

    @pytest.mark.parametrize("val, expect",[
        ("GuO3_IIhLrNHJvP5BCsJ", True),
        ('', False),
        ("OR 1=1", False),
        (123, False)
    ], ids=["correct", 'empty', "injection", "not_str"])
    def test_correct_chat_id_value(self, val, expect):
        assert MessageFromWebhook(chat_id=val).correct_chat_id() == expect


    @pytest.mark.parametrize("val, expect",[
        (123, True),
        ('', False),
        (-123, False),
        (0, False),
        (None, False),
    ], ids=["correct", 'empty', "negative", "zero", "None"])
    def test_correct_positive_int_value(self, val, expect):
        assert MessageFromWebhook().correct_positive_int_value(val) == expect


    @pytest.mark.parametrize("val, expect",[
        (None, True),
        ('missed', True),
        ("m1ss10d", False),
        ('', False),
        (123, False),
        (0, False),
    ], ids=["no_call", "missed", "incorrect_status", "empty", "not_str", "zero"])
    def test_correct_call_value(self, val, expect):
        assert MessageFromWebhook(call=val).correct_call() == expect

    def test_create_message_from_null(self):
        with pytest.raises(MessageFieldsException):
            MessageFromWebhook().create()

    def test_create_message_with_invalid_fields(self, correct_message_factory, logger_off):
        msg =  correct_message_factory()
        msg["chat_id"] = 123

        result = MessageFromWebhook(msg).create()

        assert result is False

    @pytest.mark.parametrize("msg",[
        {},
        '',
        'a',
        {"author_id": "sn123"},
        {"author_id": 123, "chat_id": 123},
        {'custom_field': 'value'},
    ], ids=["empty_dict", "not_val", "not_dict", "wrong_key_value", "correct_and_wrong_value", "no_needed_keys",])
    def test_raised_exception_error_due_to_incorrect_message(self, msg):
        with pytest.raises(MessageFieldsException):
            MessageFromWebhook(msg).create()

    @pytest.mark.parametrize("wc, ii, t, r",[
        [True, True, True, True],
        [True, True, True, False],
        [True, True, False, True],
        [True, False, True, True],
        [False, True, True, True],
    ])
    def test_unpack_str_msg(self, correct_message_factory, wc, ii, t, r):
        d = {
            "with_call": wc,
            "item_id": ii,
            "text": t,
            "read": r
        }
        msg_data = correct_message_factory(**d)
        msg = MessageFromWebhook(msg_data).create()
        msg_str = MessageFromWebhook(msg_data).create_str()

        assert MessageFromWebhook().unpack_str_msg(msg_str) == msg

    @pytest.mark.parametrize("text",[
        "Something text: you know",
        "Something text: you know; but:yoy--NO",
        "Something text: you know; but:yoy--NO~67"
    ])
    def test_unpack_str_msg_with_strange_text(self, correct_message_factory, text):
        msg_data = correct_message_factory(text=True)
        msg_data["content"]["text"] = text

        msg = MessageFromWebhook(msg_data).create()
        msg_str = MessageFromWebhook(msg_data).create_str()
        assert msg["text"] == text
        assert MessageFromWebhook().unpack_str_msg(msg_str) == msg


@pytest.mark.usefixtures("logger_off")
class TestSendEmail:
    @pytest.mark.slow
    def test_create_email(self):
        previous_one = ["<178767700603.3480.993@Taptop.lan>"]
        previous = ["<178767700603.3480.993@Taptop.lan>", "<178767700603.3480.93@Taptop.lan>"]
        assert isinstance(ShopEmail("a.@a.ru").create_mail(), MIMEMultipart)
        assert isinstance(ShopEmail("a.@a.ru", "").create_mail(), MIMEMultipart)
        assert isinstance(ShopEmail("a@a.ru", "Тема").create_mail(), MIMEMultipart)
        assert isinstance(ShopEmail("a@a.ru", "Тема", "text").create_mail(), MIMEMultipart)
        assert isinstance(ShopEmail("a@a.ru", "Тема").create_mail(previous_one), MIMEMultipart)
        assert isinstance(ShopEmail("a.@a.ru", "Тема").create_mail(previous), MIMEMultipart)

        incorrect_previous_mail = ShopEmail("a.@a.ru", "Тема").create_mail([""]).values()
        assert "In-Reply-To" not in incorrect_previous_mail
        assert 'References' not in incorrect_previous_mail

    @pytest.mark.parametrize("to, subject, text", [
        ("", "sub", None),
        ("@mail.ru", "sub", None),
        ("a@mailru", "sub", None),
        ("a@@mailru", "sub", None),
        ("a!@a.ru", "sub", None),
        ("a@a.ru", "sub", 123),
    ], ids=["no_email", "no_email_name", "no_domain_zone", "many_@", "incorrect_char", "incorrect_text"])
    def test_unable_to_create_email(self, to, subject, text):
        with pytest.raises(InvalidMailFieldException):
            ShopEmail(to, subject, text).create_mail()

    @pytest.mark.parametrize("to, subject, text", [
        (b"a@mail.ru", "sub", None),
        ("a@a.ru", 123, None),
        (None, None, None),
    ], ids=["wrong_email", "wrong_subjects", "null_fields"])
    def test_incorrect_fields_email(self, to, subject, text):
        with pytest.raises(CreateMailException):
            ShopEmail(to, subject, text).create_mail()

    def test_correct_validation_mails_ids(self):
        mails_ids = ["<178767700603.3480.993@Taptop.lan>"]
        assert ShopEmail.valid_mails_ids(mails_ids) is None

    @pytest.mark.parametrize("mails_ids", [
        ["!<178767700603.3480.993@Taptop.lan>"],
        [" "],
        [""]
    ], ids=["incorrect_char", "probel", "empty_str"])
    def test_failed_validation_runtime_mails_ids(self, mails_ids):
        with pytest.raises(InvalidMailFieldException):
            ShopEmail.valid_mails_ids(mails_ids)

    @pytest.mark.parametrize("mails_ids",[
        [],
        [123],
        "<>",
    ], ids=["empty_list", "wrong_type_mail_id", "not_a_list"])
    def test_failed_validation_mails_ids(self, mails_ids):
        with pytest.raises(CreateMailException):
            ShopEmail.valid_mails_ids(mails_ids)


class TestSMTPEmailSender:
    @pytest.fixture
    def sender(self):
        return SMTPEmailSender(
            from_email="sender@example.com",
            password="password",
        )

    @pytest.fixture
    def mail(self):
        msg = MIMEMultipart()
        msg["To"] = "recipient@example.com"
        msg["Message-ID"] = "<test-message-id@example.com>"
        return msg

    def test_connect(self, sender, mocker, logger_off):
        client = mocker.MagicMock()
        smtp_ssl_mock = mocker.patch(
            "chat.utils.smtplib.SMTP_SSL",
            return_value=client,
        )
        sender.connect()
        smtp_ssl_mock.assert_called_once_with(
            "smtp.yandex.com",
            465,
            context=sender.ctx,
            timeout=7,
        )
        client.login.assert_called_once_with(
            "sender@example.com",
            "password",
        )
        assert sender.client is client

    def test_send_connects_if_client_is_none(self, sender, mail, mocker, logger_off):
        client = mocker.MagicMock()
        mocker.patch(
            "chat.utils.smtplib.SMTP_SSL",
            return_value=client,
        )
        sender.send(mail)
        client.login.assert_called_once_with(
            "sender@example.com",
            "password",
        )
        client.sendmail.assert_called_once_with(
            "sender@example.com",
            "recipient@example.com",
            mail.as_string(),
        )

    def test_send_uses_existing_connection(self, sender, mail, mocker, logger_off):
        client = mocker.MagicMock()
        sender.client = client
        connect_mock = mocker.patch.object(
            sender,
            "connect",
        )
        sender.send(mail)
        connect_mock.assert_not_called()
        client.sendmail.assert_called_once_with(
            "sender@example.com",
            "recipient@example.com",
            mail.as_string(),
        )

    def test_send_reconnects_after_disconnect(self, sender, mail, mocker, caplog):
        old_client = mocker.MagicMock()
        new_client = mocker.MagicMock()

        sender.client = old_client
        old_client.sendmail.side_effect = smtplib.SMTPServerDisconnected()

        close_mock = mocker.patch.object(
            sender,
            "close",
        )

        def reconnect():
            sender.client = new_client

        connect_mock = mocker.patch.object(
            sender,
            "connect",
            side_effect=reconnect,
        )

        with caplog.at_level(logging.WARNING, logger="chat_logger"):
            sender.send(mail)

        close_mock.assert_called_once()
        connect_mock.assert_called_once()
        old_client.sendmail.assert_called_once()
        new_client.sendmail.assert_called_once_with(
            "sender@example.com",
            "recipient@example.com",
            mail.as_string(),
        )
        assert any(
            record.name == "chat_logger"
            and record.levelno == logging.WARNING
            and "connection lost, reconnecting" in record.message.lower()
            for record in caplog.records
        )

    def test_close_without_client(self, sender, logger_off):
        sender.client = None
        sender.close()
        assert sender.client is None

    def test_close_quits_client(self, sender, mocker, logger_off):
        client = mocker.MagicMock()
        sender.client = client

        sender.close()

        client.quit.assert_called_once()
        assert sender.client is None

    def test_close_clears_client_even_if_quit_fails(self, sender, mocker, logger_off):
        client = mocker.MagicMock()
        client.quit.side_effect = RuntimeError("quit failed")
        sender.client = client

        with pytest.raises(RuntimeError, match="quit failed"):
            sender.close()
        assert sender.client is None

    def test_context_manager_connects_and_closes(self, sender, mocker, logger_off):
        connect_mock = mocker.patch.object(sender, "connect")
        close_mock = mocker.patch.object(sender, "close")
        with sender as result:
            assert result is sender

        connect_mock.assert_called_once()
        close_mock.assert_called_once()

    def test_exit_returns_false(self, sender, mocker, logger_off):
        close_mock = mocker.patch.object(sender, "close")

        result = sender.__exit__(
            ValueError,
            ValueError("test"),
            None,
        )
        close_mock.assert_called_once()
        assert result is False


class TestValidMailsIds:
    def test_valid_mails(self):
        mails = ["<abc.123@example.com>", "<def.334.@example.com>",]
        ShopEmail.valid_mails_ids(mails)

    @pytest.mark.parametrize("val, expect", [
        ("abc@example.com", "mails is not a list"),
        ([], "not mails in list"),
        ([123], "mail_id is not a str"),
    ], ids=["list", "cant be empty", "string"])
    def test_mails_must_be(self, val, expect):
        with pytest.raises(CreateMailException, match=expect):
            ShopEmail.valid_mails_ids(val)

    @pytest.mark.parametrize("val, expect", [
        (["   "], "mail_id is empty"),
        ([""], "mail_id is empty"),
        (["<abc@example.com>!"], "mail_id contain invalid characters"),
    ], ids=["be_empty_cause_spaces", "be_empty", "contain_invalid_characters"])
    def test_mail_id_cannot(self, val, expect):
        with pytest.raises(InvalidMailFieldException, match=expect):
            ShopEmail.valid_mails_ids(val)


class TestValidEmail:
    @pytest.mark.parametrize("email",[
        "test@example.com",
        "john.doe@example.com",
        "user123@domain.org",
    ])
    def test_valid_email(self, email):
        assert ShopEmail.valid_email(email) is True

    @pytest.mark.parametrize("email",[
        "",
        "test",
        "test@example",
        "test@example.",
        "test@example.3",
        "test@",
        "@example.com",
        "123test@example.com",
        "test-name@example.com",
        "test_name@example.com",
        "test name@example.com",
        "test@example@com",
        ],
        ids=[
        "empty",
        "text",
        "no_domain_name",
        "no_domain_name",
        "domain_name_incorrect",
        "no_sandbox",
        "no_name",
        'starts_with_digest',
        "invalid_char",
        "invalid_char",
        "invalid_char",
        "duble @",
])
    def test_invalid_email(self, email):
        assert ShopEmail.valid_email(email) is False

    @pytest.mark.parametrize("email",[
        None, 123, [], {}, b"",
    ])
    def test_email_must_be_string(self, email):
        with pytest.raises(CreateMailException, match="email is not a str"):
            ShopEmail.valid_email(email)


class TestCreateMail:
    @pytest.mark.slow
    def test_create_mail(self, shop_email):
        mail = shop_email.create_mail()

        assert isinstance(mail, MIMEMultipart)
        assert mail["From"] == shop_email.from_email
        assert mail["To"] == "recipient@example.com"
        assert mail["Subject"] == "Hello"
        assert mail["Message-ID"]
        assert "Test message" in mail.as_string()

    @pytest.mark.slow
    def test_create_mail_without_text(self):
        email = ShopEmail(to_email="recipient@example.com", subject="Hello")
        mail = email.create_mail()

        assert mail["Subject"] == "Hello"
        assert mail["To"] == "recipient@example.com"

    @pytest.mark.slow
    def test_subject_defaults_to_empty_string(self):
        email = ShopEmail(to_email="recipient@example.com")
        mail = email.create_mail()

        assert mail["Subject"] == ""

    def test_subject_must_be_string(self, shop_email):
        shop_email.subject = 123
        with pytest.raises(CreateMailException, match="subject is not a str"):
            shop_email.create_mail()

    def test_invalid_recipient_email(self):
        email = ShopEmail(
            to_email="invalid-email",
            subject="Hello",
            text="Hello",
        )
        with pytest.raises(InvalidMailFieldException, match="Head of email is invalid"):
            email.create_mail()

    def test_invalid_text_type(self, shop_email):
        shop_email.text = 123
        with pytest.raises(InvalidMailFieldException, match="Head of email is invalid"):
            shop_email.create_mail()

    @pytest.mark.slow
    def test_reply_mail(self, shop_email):
        previous_mails = ["<first@example.com>", "<second@example.com>"]
        mail = shop_email.create_mail(previous_mails)

        assert mail["Subject"] == "Re: Hello"
        assert mail["In-Reply-To"] == "<second@example.com>"
        assert mail["References"] == "<first@example.com> <second@example.com>"

    @pytest.mark.slow
    def test_reply_uses_last_message_as_in_reply_to(self, shop_email):
        previous_mails = [ "<one@example.com>", "<two@example.com>", "<three@example.com>"]
        mail = shop_email.create_mail(previous_mails)

        assert mail["In-Reply-To"] == "<three@example.com>"

    @pytest.mark.slow
    @pytest.mark.parametrize("prev_mails", [
        ["<invalid@example.com>!"],
        []
    ], ids=["invalid_char", "empty"])
    def test_invalid_previous_mails_do_not_break_creation(self, shop_email, prev_mails, logger_off):
        mail = shop_email.create_mail(prev_mails)

        assert mail["Subject"] == "Hello"
        assert mail["In-Reply-To"] is None
        assert mail["References"] is None

    def test_message_id_is_generated(self, shop_email, mocker):
        make_msgid_mock = mocker.patch(
            "chat.utils.make_msgid",
            return_value="<generated@example.com>",
        )

        mail = shop_email.create_mail()

        make_msgid_mock.assert_called_once_with(
            # EMAIL_DOMAIN_NAME
            mocker.ANY,
        )
        assert mail["Message-ID"] == "<generated@example.com>"


class TestSendEmailFromYandex:
    @pytest.fixture
    def shop_email(self):
        return ShopEmail(
            to_email="recipient@example.com",
            subject="Hello",
            text="Hello",
        )

    @pytest.fixture
    def mail(self):
        msg = MIMEMultipart()
        msg["To"] = "recipient@example.com"
        msg["Message-ID"] = "<message@example.com>"
        return msg

    def test_send_emails_successfully(self, shop_email, mail, mocker):
        sender = mocker.MagicMock()
        sender_class = mocker.patch("chat.utils.SMTPEmailSender")
        sender_class.return_value.__enter__.return_value = sender

        result = shop_email.send_email_from_yandex([mail])

        sender_class.assert_called_once_with(
            shop_email.from_email,
            shop_email.password,
            "smtp.yandex.com",
            465,
            7,
        )
        sender.send.assert_called_once_with(mail)
        assert result == [("<message@example.com>", True, None)]

    def test_send_multiple_emails(
        self,
        shop_email,
        mocker,
    ):
        mail1 = MIMEMultipart()
        mail1["To"] = "one@example.com"
        mail1["Message-ID"] = "<one@example.com>"

        mail2 = MIMEMultipart()
        mail2["To"] = "two@example.com"
        mail2["Message-ID"] = "<two@example.com>"

        sender = mocker.MagicMock()
        sender_class = mocker.patch("chat.utils.SMTPEmailSender")
        sender_class.return_value.__enter__.return_value = sender

        result = shop_email.send_email_from_yandex([mail1, mail2])

        assert result == [("<one@example.com>", True, None), ("<two@example.com>", True, None)]
        assert sender.send.call_count == 2

    @pytest.mark.parametrize("type_error", [
        smtplib.SMTPException("SMTP error"),
        RuntimeError("unexpected error")
    ])
    def test_smtp_exception_is_reraised(
        self,
        shop_email,
        mail,
        mocker,
        type_error,
        logger_off
    ):
        sender = mocker.MagicMock()
        sender.send.side_effect = type_error
        sender_class = mocker.patch("chat.utils.SMTPEmailSender")
        sender_class.return_value.__enter__.return_value = sender


        results = shop_email.send_email_from_yandex([mail])

        sender.send.assert_called_once_with(mail)
        assert results == [(mail["Message-ID"], False, type_error)]

    def test_send_multiple_emails_with_success_and_failure(
            self,
            shop_email,
            mocker,
            logger_off
    ):
        mail1 = MIMEMultipart()
        mail1["To"] = "one@example.com"
        mail1["Message-ID"] = "<one@example.com>"

        mail2 = MIMEMultipart()
        mail2["To"] = "two@example.com"
        mail2["Message-ID"] = "<two@example.com>"

        smtp_error = smtplib.SMTPException("SMTP error")

        sender = mocker.MagicMock()
        sender.send.side_effect = [None, smtp_error]
        sender_class = mocker.patch("chat.utils.SMTPEmailSender")
        sender_class.return_value.__enter__.return_value = sender

        results = shop_email.send_email_from_yandex([mail1, mail2])

        sender.send.assert_has_calls([
            mocker.call(mail1),
            mocker.call(mail2),
        ])
        assert sender.send.call_count == 2
        assert results == [
            ("<one@example.com>", True, None),
            ("<two@example.com>", False, smtp_error),
        ]
