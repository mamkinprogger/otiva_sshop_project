import random
import string
import time

import pytest

from chat.utils import MessageFromWebhook, MessageFieldsException


@pytest.fixture
def correct_message_factory():
    def create_correct_message(with_call=False, item_id=True, text=True):
        msg = {
            "author_id": random.randint(1, 1_000_000_000_000),
            "chat_id": ''.join(random.choice(string.ascii_letters + string.digits+"-_") for _ in range(30)),
            "created": int(time.time()),
            "item_id": random.randint(1, 1_000_000_000_000) if item_id else None,
            "content": {}

        }
        if with_call:
            msg["content"] = {
                "call": {
                    "status": "missed",
                    "target_user_id": 94235311
                }
            }
        if text:
            msg["content"]["text"] = "Something text"

        return msg
    return create_correct_message


class TestMessageFromWebhook:
    def test_create_message_data_for_manager(self, correct_message_factory):
        res = MessageFromWebhook(correct_message_factory(with_call=True, item_id=True)).create()
        assert isinstance(res, dict)
        assert isinstance(res.get("client_id"), int)
        assert isinstance(res.get("chat_id"), str)
        assert isinstance(res.get("sending_time"), int)
        assert isinstance(res.get("call"), str)
        assert isinstance(res.get("item_id"), int)

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
        ('', False),
        (123, False),
        (0, False),
    ], ids=["no_call", "missed", "empty", "not_str", "zero"])
    def test_correct_call_value(self, val, expect):
        assert MessageFromWebhook(call=val).correct_call() == expect

    def test_create_message_from_null(self):
        with pytest.raises(MessageFieldsException):
            MessageFromWebhook().create()

    @pytest.mark.parametrize("msg",[
        {},
        '',
        {"author_id": "sn123"},
        {"author_id": 123, "chat_id": 123},
        {'custom_field': 'value'}
    ], ids=["empty_dict", "not_dict", "wrong_key_value", "correct_and_wrong_value", "no_needed_keys"])
    def test_raised_exception_error_due_to_incorrect_message(self, msg):
        with pytest.raises(MessageFieldsException):
            MessageFromWebhook(msg).create()


class TestSendEmail:
    pass

