import random
import string
import time

import pytest

@pytest.fixture
def correct_message_factory():
    def create_correct_message(with_call=False, item_id=True, text=True, read=False):
        msg = {
            "author_id": random.randint(1, 1_000_000_000_000),
            "chat_id": ''.join(random.choice(string.ascii_letters + string.digits+"-_") for _ in range(30)),
            "created": int(time.time()),
            "item_id": random.randint(1, 1_000_000_000_000) if item_id else None,
            "content": {},
            "read": None if not read else int(time.time() + 1),
            "id": "".join(random.choice(string.ascii_letters) for _ in range(30)),
        }
        if with_call:
            msg["content"] = {
                "call": {
                    "status": "missed",
                    "target_user_id": 94235311
                }
            }
        else:
            msg["content"] = {"call": None}
        if text:
            msg["content"]["text"] = "Something text"

        return msg
    return create_correct_message
