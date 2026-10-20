import concurrent.futures
import logging
import smtplib
import sys
import time
from email.utils import make_msgid
from multiprocessing import get_context

from app.misc.celery_misc import celery
from app.misc.redis_misc import redis_broker, RedisLocker
from app.settings import EMAIL_DOMAIN_NAME, MIN_MAIL_ID_COUNT
from chat.notifications.email_sending import send_notifications_on_email, load_and_extend_data_for_email
from chat.utils import MessageFromWebhook

logger = logging.getLogger("celery_logger")
logger_shipping = logging.getLogger("celery_logger_shipping")


def get_send_shipping(start_time: float, celery_start_command: list[str]):
    for i in celery_start_command:
        if "--loglevel" in i:
            level = i.split("=")[1].upper()
            if level in ["WARNING", "ERROR"]:
                time_ms = int(round(time.perf_counter() - start_time, 3) * 1000)
                pretty_time = "{}.{:03d}".format(time_ms // 1000, time_ms % 1000)
                logger_shipping.error(f"shipping took {pretty_time} seconds")


def lmove_entities(pending_key: str, processing_key: str, max_msgs=15) -> list[bytes]:
    """
    LMOVE entities from PENDING_KEY to PROCESSING_KEY.

    max_msgs - maximum number of messages to keep. It means set limit msgs for worker
    """
    result = []
    while len(result) < max_msgs:
        msg_entity = redis_broker.lmove(pending_key, processing_key, "RIGHT", "LEFT")
        if msg_entity is None:
            break
        result.append(msg_entity)
    return result


def unpack_msgs(msg_entities: list[bytes], max_emails: int) -> tuple[dict[bytes, dict], list[bytes]]:
    """
    Unpack raw_str MessagesFromWebhook

    If count of emails from one chat > max_emails adds messages exceeding the limit to the remove entity.

    :returns: (dict[bytes[raw_message], dict], list[bytes[remove_messages]])
    """
    messages = dict()
    remove_messages = []

    viewed = dict()
    for msg_entity in msg_entities:
        new_chat, _, msg_data = msg_entity.decode().partition(";")
        message = MessageFromWebhook().unpack_str_msg(msg_data)
        chat_id = message["chat_id"]
        count = viewed.get(chat_id, 0)

        message["skipped_msgs"] = 0
        message["new_chat"] = new_chat == "new_chat=True" if count == 0 else False
        if count + 1 > max_emails:
            remove_messages.append(msg_entity)
        else:
            messages[msg_entity] = message
        viewed[chat_id] = count + 1

    for chat in viewed:
        count = viewed[chat]
        for msg in messages.values():
            if msg["chat_id"] == chat:
                msg["skipped_msgs"] = count - max_emails if count > max_emails else 0
                break
    return messages, remove_messages


def choose_messages(
    msgs_key: str,
    processing_key: str,
    max_emails: int = 2,
) -> tuple[list[dict], list[bytes]]:
    """
    Move all messages from pending queue to processing queue,
    Fetches missing values from processing key

    return (list[dict], list[values in processing_key])

    Messages which exceeded max_emails are removed
    """
    messages: list[dict] = []
    raw_messages: list[bytes] = []
    remove_messages = []

    processing_msgs = redis_broker.lrange(processing_key, 0, -1)
    pending_msgs = lmove_entities(msgs_key, processing_key)

    for i in [processing_msgs, pending_msgs]:
        msgs, rm_msgs = unpack_msgs(i, max_emails)
        for raw_message, message in msgs.items():
            messages.append(message)
            raw_messages.append(raw_message)
        remove_messages.extend(rm_msgs)

    if remove_messages:
        with redis_broker.pipeline() as pipe:
            [pipe.lrem(processing_key, 0, msg) for msg in remove_messages]
            pipe.execute()
    return messages, raw_messages


def send_manager(manager_id: int, manager_email: str, messages: list[dict]) -> list[bytes | None]:
    """
    Send notification to manager

    return [Messages_in_processing_key, Failed_Messages]

    Failed messages are those that failed with an SMTPException.

    :return: (list[str[msgs]], list[str[failed_msgs]])
    """
    messages_data = load_and_extend_data_for_email(manager_id, messages)

    create_mail_id_task.delay() # prepare email_id
    res_sending = send_notifications_on_email(
        manager_email,
        emails_data=[(i["client_id"], i["topic"], i["prev_email"]) for i in messages_data.values()],
        alias_keys=[i for i in messages_data],
        view_result=True,
    )

    retries = []
    for res in res_sending:
        if len(res) != 3:
            continue
        msg = messages_data[res[0]]
        fail_type = res[2]
        if isinstance(fail_type, smtplib.SMTPException):
            msg_str = MessageFromWebhook(msg).create_str()
            retries.append(f"new_chat={msg["new_chat"]};{msg_str}")
    return retries

# можно тоже перекинуть к RedisMyClass; и через *argv получать количество значений в ключах
def get_manager_messages(pending_key: str, processing_key: str) -> list[int]:
    with redis_broker.pipeline() as pipe:
        pipe.llen(pending_key)
        pipe.llen(processing_key)
        msgs = pipe.execute()
    return msgs


@celery.task(
    bind=True,
    ignore_result=True,
    max_retries=8,
    default_retry_delay=8,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_notification_task(self, manager: int, manager_email: str):
    start_task = time.perf_counter()
    manager_key = str(manager)
    processing_key = f"{manager}:processing"

    msgs = get_manager_messages(manager_key, processing_key)
    if sum(msgs) == 0:
        logger.info(f"Messages for {manager} already sent")
        return

    locker = RedisLocker(redis_broker)
    lock = locker.create_lock_key(manager_key)
    if lock is None:
        logger.info(f"Manager {manager} is locked, retrying later")
        raise self.retry()

    try:
        messages, raw_messages = choose_messages(manager_key, processing_key)
        fails = send_manager(manager, manager_email, messages)
        if fails:
            redis_broker.lpush(f"{manager_key}:retry", *fails)
            notification_retry_task.apply_async((manager, manager_email), countdown=5)
        with redis_broker.pipeline() as pipe:
            [pipe.lrem(processing_key, 0, msg_entity) for msg_entity in raw_messages]
            pipe.execute()
    except Exception as e:
        logger.error(f"SendNotf_Task {repr(e)}", exc_info=True)
    finally:
        locker.release_locking(lock)
        get_send_shipping(start_task, sys.argv)


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=8,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def notification_retry_task(self, manager: int, manager_email: str):
    start_task = time.perf_counter()
    manager_key = f"{manager}:retry"
    processing_key = f"{manager_key}:processing"

    msgs = get_manager_messages(manager_key, processing_key)
    if sum(msgs) == 0:
        logger.info(f"Retries for {manager_key} already done")
        return

    locker = RedisLocker(redis_broker)
    lock = locker.create_lock_key(manager_key)
    if lock is None:
        logger.info(f"Manager {manager_key} is locked, retrying later")
        raise self.retry()

    try:
        messages, raw_messages = choose_messages(manager_key, processing_key)
        fails = send_manager(manager, manager_email, messages)
        for msg in fails:
            raw_messages.remove(msg)
        with redis_broker.pipeline() as pipe:
            [pipe.lrem(processing_key, 0, msg_entity) for msg_entity in raw_messages]
            pipe.execute()
    except Exception as e:
        logger.error(f"RetryMsg_Task {repr(e)}", exc_info=True)
    else:
        if fails and self.request.retries < self.max_retries:
            raise self.retry()
    finally:
        locker.release_locking(lock)
        get_send_shipping(start_task, sys.argv)


@celery.task
def create_mail_id_task():
    ids_count = redis_broker.llen("mails_ids")
    if ids_count >= MIN_MAIL_ID_COUNT:
        return

    create_key = "creating_mails_ids"
    locker = RedisLocker(redis_broker)
    lock = locker.create_lock_key(create_key)
    if lock is None:
        logger.info(f"Creating mails id is running")
        return

    try:
        cxt = get_context('spawn')
        with concurrent.futures.ProcessPoolExecutor(max_workers=8, mp_context=cxt) as executor:
            futures = [executor.submit(make_msgid, EMAIL_DOMAIN_NAME) for _ in range(100)]

            for future in concurrent.futures.as_completed(futures):
                if future.exception():
                    continue
                msg_id = future.result()
                redis_broker.lpush("mails_ids", msg_id)
    except Exception as e:
        logger.error(f"CreateMsgsIds_Task {repr(e)}", exc_info=True)
    finally:
        locker.release_locking(lock)
