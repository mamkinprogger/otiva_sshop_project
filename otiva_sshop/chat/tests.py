import random
import string
import time

import pytest

from chat.utils import MessageFromWebhook, MessageFieldsException


@pytest.fixture
def correct_message_factory():
    def create_correct_message(with_call=False, item_id=True):
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
        return msg
    return create_correct_message


class TestMessageFromWebhook:
    def test_create_message_data_for_manager(self, correct_message_factory):
        res = MessageFromWebhook(correct_message_factory(with_call=True, item_id=True)).create()
        assert isinstance(res, dict)
        assert isinstance(res["client_id"], int)
        assert isinstance(res["chat_id"], str)
        assert isinstance(res["sending_time"], int)
        assert isinstance(res["call"], str)
        assert isinstance(res["item_id"], int)

    def test_create_message_data_for_manager_without_call(self, correct_message_factory):
        res = MessageFromWebhook(correct_message_factory(with_call=False)).create()
        assert res["call"] is None

    def test_create_message_data_for_manager_without_item_id(self, correct_message_factory):
        res = MessageFromWebhook(correct_message_factory(item_id=False)).create()
        assert res["item_id"] is None


    @pytest.mark.parametrize("val, expect",[
        ("GuO3_IIhLrNHJvP5PBCsJ", True),
        ('', False),
        ("OR 1=1", False),
        (123, False)
    ], ids=["correct", 'empty', "injection", "not_str"])
    def test_correct_chat_id(self, val, expect):
        assert MessageFromWebhook().correct_chat_id(val) == expect


    @pytest.mark.parametrize("val, expect",[
        (123, True),
        ('', False),
        (-123, False),
        (0, False),
        (None, False),
    ])
    def test_correct_positive_int_value(self, val, expect):
        assert MessageFromWebhook().correct_positive_int_value(val) == expect


    @pytest.mark.parametrize("val, expect",[
        (None, True),
        ('missed', True),
        ('', False),
        (123, False),
        (0, False),
    ])
    def test_correct_call(self, val, expect):
        assert MessageFromWebhook().correct_call(val) == expect


    def test_runtime_error(self):
        with pytest.raises(RuntimeError):
            MessageFromWebhook().create()
        with pytest.raises(RuntimeError):
            MessageFromWebhook({}).create()
        with pytest.raises(RuntimeError):
            MessageFromWebhook('').create()

    def test_create_messagefromwebhook_instance(self):
        with pytest.raises(MessageFieldsException):
            MessageFromWebhook('s')
        with pytest.raises(MessageFieldsException):
            MessageFromWebhook({'custom_field': 'value'})

