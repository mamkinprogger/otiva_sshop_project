from email.mime.multipart import MIMEMultipart

import pytest

from chat.utils import MessageFromWebhook, MessageFieldsException, CreateMailException, ShopEmail, \
    InvalidMailFieldException


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

    def test_create_message_with_invalid_fields(self, correct_message_factory):
        msg =  correct_message_factory()
        msg["chat_id"] = 123
        assert MessageFromWebhook(msg).create() is False

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


class TestSendEmail:

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


