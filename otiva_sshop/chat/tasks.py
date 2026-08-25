import logging

from app.misc.celery import celery_client
from chat.db_orm import orm_update_manager_load
from chat.notifications.email_sending import send_on_email
from goods.db_orm import orm_get_avito_product

logger = logging.getLogger("celery_logger")

# TODO разобраться с retries


@celery_client.task(
    max_retries=5,
    default_retry_delay=10,
    retry_jitter=True,
)
def send_message_to_manager(manager: int, manager_email: str, message: dict, new_chat: bool):
    client_id, previous_emails = orm_update_manager_load(manager, message["client_id"], message["chat_id"], message["call"], new_chat)
    product = "НеОбъявление"
    if "item_id" in message:
        product = orm_get_avito_product(message["item_id"])
    topic = f"{product}-{message["chat_id"]}"

    send_on_email(
        client_id,
        manager_email,
        topic,
        previous_emails,
    )
