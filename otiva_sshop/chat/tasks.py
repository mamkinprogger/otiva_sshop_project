import logging
import smtplib
import uuid
import concurrent.futures

from app.misc.celery import celery_client
from app.misc.redis_misc import redis_client_broker
from chat.db_orm import orm_update_manager_load

from chat.utils import MessageFromWebhook
from chat.notifications.email_sending import send_notification_on_email
from goods.db_orm import orm_get_avito_product

logger = logging.getLogger("celery_logger")

class EmailForManager:
    def __init__(self, manager_id: int, messages: list):
        """Modifies elements in messages"""

        if not isinstance(messages, list):
            raise TypeError("messages must be a list")
        elif not isinstance(manager_id, int):
            raise TypeError("manager_id must be an integer")

        self.manager_id = manager_id
        self.messages = {ind: msg for ind, msg in enumerate(messages)}

    def get_topic_and_prev_emails(
            self,
            client_id: int,
            chat_id: str,
            call: str | None,
            new_chat: bool,
            item_id: int | None,
    ) -> tuple[bool, str, list[str]]:
        """
        Update manager load and get previous mail from client
        If item_id passed, check existing item_id
        """
        just_added, previous_emails = orm_update_manager_load(self.manager_id, client_id, chat_id, call, new_chat)
        product = "НеОбъявление" # TODO убрать клиента из redis:create_chat
        if item_id:
            product = orm_get_avito_product(item_id)
        topic = f"{product}-{chat_id}"
        return just_added, topic, previous_emails


    def append_emails_fields_from_wk_message(self):
        """
        Extends the dictionary passed to the manager with `topic` and `prev_emails` fields.

        Removes invalid messages from the array.

        Makes db queries
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                [
                    sequence,
                    executor.submit(
                        self.get_topic_and_prev_emails,
                        message["client_id"], message["chat_id"],
                        message["call"], message["new_chat"], message["item_id"]
                    )
                ]
                for sequence, message in self.messages.items()
            ]
            for sequence, future in futures:
                if future.exception() is not None:
                    self.messages.pop(sequence)
                    logger.error(repr(future.exception()))
                else:
                    _, topic, prev_emails = future.result()
                    self.messages[sequence]["topic"] = topic
                    self.messages[sequence]["prev_emails"] = prev_emails

    def create_email_fields(self):
        self.append_emails_fields_from_wk_message()
        return self.messages

    def __str__(self):
        return f"{self.manager_id}:{[i for i in self.messages]}"



def release_manager_lock(lock_key: str, lock_token: str) -> None:
    release_lock_script = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    redis_client_broker.eval(
        release_lock_script,
        1,
        lock_key,
        lock_token,
    )


def choose_messages(msgs_key: str, max_emails=2) -> list[dict]:
    """
    Choose messages to send.

    Max emails -> maximum number of notifications per chat

    :returns: list[msg_dict]
    """
    viewed = dict()
    msgs = []

    msg_entity = redis_client_broker.rpop(msgs_key)
    while msg_entity:
        new_chat, _, msg_data = msg_entity.decode().partition(";")
        message = MessageFromWebhook.unpack_str_msg(msg_data)

        count = viewed.get(message["chat_id"], 0)
        if count+1 > max_emails and not message["read"]:
            pass
        else:
            message["new_chat"] = new_chat == "new_chat=True" if count == 0 else False
            msgs.append(message)
            viewed[message["chat_id"]] = count + 1
        msg_entity = redis_client_broker.rpop(msgs_key)

    return msgs


@celery_client.task(
    bind=True,
    ignore_result=True,
    max_retries=8,
    default_retry_delay=8,
    retry_jitter=True,
    # acks_late=True,; не терять смски при worker kill. сделать pending-messages,processing-messages(lmove/blmove) в redis
    reject_on_worker_lost=True,
)
def send_message_to_manager(self, manager: int, manager_email: str):
    s_manager = str(manager)
    lock_key = f"{manager}_lock"
    lock_token = str(uuid.uuid4())

    if redis_client_broker.llen(s_manager) == 0:
        logger.info(f"Messages for {manager}  already send")
        return
    elif not redis_client_broker.set(lock_key, lock_token, nx=True, ex=60):
        logger.info(f"Manager {manager} is locked, retrying later")
        raise self.retry()

    try:
        messages = EmailForManager(manager, choose_messages(s_manager)).create_email_fields()
        res_sending = send_notification_on_email(
            manager_email,
            emails_data=[(i["client_id"], i["topic"], i["prev_emails"]) for i in messages.values()],
            alias_keys=[i for i in messages],
            view_result=True,
        )

        retries = []
        for res in res_sending:
            if len(res) != 3:
                continue
            msg = messages[res[0]]
            fail_type = res[2]
            if isinstance(fail_type, smtplib.SMTPException):
                retries.append(MessageFromWebhook(msg).create_str())
            else:
                logger.info(f"Другая ошибка: {repr(fail_type)}")
        logger.info(f"Сообщения на повторную отправку {retries}")

    except Exception as e:
        logger.error(repr(e), exc_info=True)
    finally:
        release_manager_lock(lock_key, lock_token)
