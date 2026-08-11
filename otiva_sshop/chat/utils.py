import logging

logger = logging.getLogger("chat_logger")


def create_correct_msg(msg: dict) -> dict | None:
    """
    Validate value of message
    return dict of needed message data or None if incorrect message
    """
    try:
        correct_msg = {
        "client_id": msg["author_id"],
        "chat_id": msg["chat_id"],
        "sending_time": msg["created"],
        "call": None
        }
        if msg["content"] and msg["content"]["call"]:
            correct_msg["call"] = msg["content"]["call"]["status"]

    except (KeyError, TypeError) as e:
        logger.warning(f"В полях сообщения ошибка: {repr(e)}")
        logger.error(f"Сообщение: {msg}")
        return None
    except Exception as e:
        logger.warning(
            f"Не удалось обработать сообщение ошибка: {e}",
            exc_info=True
        )
        return None

    valid_data = [
        type(correct_msg["client_id"]) is int and correct_msg["client_id"] > 0,
        isinstance(correct_msg["chat_id"], str) and correct_msg["chat_id"].isalnum(),
        type(correct_msg["sending_time"]) is int and correct_msg["sending_time"] > 0,
    ]
    if correct_msg["call"]:
        valid_data.append(
            isinstance(correct_msg["call"], str) and correct_msg["call"].isalpha()
        )

    if not False in valid_data:
        return correct_msg
    else:
        logger.info(f"Сообщение некорректно {correct_msg}")
        return None
