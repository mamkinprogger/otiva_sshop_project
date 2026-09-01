import logging
import concurrent.futures

from app.misc.celery import celery_client
from app.misc.redis_misc import redis_client_broker

from chat.notifications.email_sending import send_on_email
from chat.db_orm import orm_update_manager_load
from goods.db_orm import orm_get_avito_product

logger = logging.getLogger("celery_logger")


def get_topic_and_prev_emails(
        manager: int,
        client_id: int,
        chat_id: str,
        call: str | None,
        new_chat: bool,
        item_id: int | None,
) -> tuple[int, str, list[str]]:
    """
    Update manager load and get previous mail from client
    If item_id passed, check existing item_id

    :param manager: id of manager
    :param client_id: id of client
    :param chat_id:
    :param call: status of call
    :param new_chat:
    :param item_id:
    :return:
    """
    client_id, previous_emails = orm_update_manager_load(manager, client_id, chat_id, call, new_chat)
    product = "НеОбъявление"
    if item_id:
        product = orm_get_avito_product(item_id)
    topic = f"{product}-{chat_id}"
    return client_id, topic, previous_emails


def choose_messages(msgs_key: str, max_emails=2) -> list[dict]:
    """Choose messages to send. Max emails -> maximum number of notifications per chat"""
    viewed = dict()
    msgs = []

    msg_entity = redis_client_broker.rpop(msgs_key)
    while msg_entity:
        msg = msg_entity.decode()
        chat_id = msg.partition(";")[0]

        count = viewed.get(chat_id, 0)
        if count < max_emails:
            viewed[chat_id] = count + 1
            msgs.append(msg)
        msg_entity = redis_client_broker.rpop(msgs_key)

    viewed = set()
    messages_list = []
    for i in msgs:
        _, new_chat, msg_data = i.split(";", 2)
        message = dict()

        for field in msg_data.split("~"):
            key, separator, value = field.partition(":")
            if separator:
                if key in ["client_id", "item_id", "sending_time"]:
                    message[key] = int(value) if value not in ("", "None") else None
                else:
                    message[key] = value if value not in ("", "None") else None
            else:
                text_value = message.get("text", "")
                message["text"] = text_value + field

        if message["chat_id"] not in viewed:
            message["new_chat"] = new_chat == "new_chat=True"
            viewed.add(message["chat_id"])
        else:
            message["new_chat"] = False
        messages_list.append(message)
    return messages_list


def create_emails_data(manager: int, messages: list[dict]) -> list[tuple[int, str, list]]:
    emails_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(
                get_topic_and_prev_emails,
                manager, message["client_id"], message["chat_id"], message["call"], message["new_chat"],
                message["item_id"]
            )
            for message in messages
        ]
        for future in futures:
            if future.exception() is not None:
                logger.error(repr(future.exception()))
            else:
                emails_data.append(future.result())
    return emails_data


@celery_client.task(
    max_retries=5,
    default_retry_delay=10,
    retry_jitter=True,
)
def send_message_to_manager(manager: int, manager_email: str):
    try:
        s_manager = str(manager)
        if not redis_client_broker.lrange(s_manager, 0, -1):
            print("no messages")
            return
        elif not redis_client_broker.setnx(f"{manager}_lock", 1):
            print("locked")
            raise RuntimeError("locked, waiting 10 secs")

        messages = choose_messages(s_manager)
        emails_data = create_emails_data(manager, messages)
        send_on_email(manager_email, emails_data)
        redis_client_broker.delete(f"{s_manager}_lock")
    except Exception as e:
        logger.error(repr(e), exc_info=True)
        redis_client_broker.delete(f"{manager}_lock")
