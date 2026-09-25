import logging
import smtplib
import uuid

from app.misc.celery_misc import celery
from app.misc.redis_misc import redis_broker

from chat.utils import MessageFromWebhook
from chat.notifications.email_sending import send_notifications_on_email, create_msgsdata_for_email

logger = logging.getLogger("celery_logger")


def release_manager_lock(lock_key: str, lock_token: str) -> None:
    """
    Delete lock_key if lock_key value is lock_token

    :param lock_key:
    :param lock_token:
    :return:
    """
    release_lock_script = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    redis_broker.eval(
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

    msg_entity = redis_broker.rpop(msgs_key)
    while msg_entity:
        new_chat, _, msg_data = msg_entity.decode().partition(";")
        message = MessageFromWebhook().unpack_str_msg(msg_data)
        count = viewed.get(message["chat_id"], 0)
        if count+1 > max_emails or message["read"]:
            pass
        else:
            message["new_chat"] = new_chat == "new_chat=True" if count == 0 else False
            msgs.append(message)
            viewed[message["chat_id"]] = count + 1
        msg_entity = redis_broker.rpop(msgs_key)

    return msgs


def send_manager(manager_id: int, manager_email: str, manager_key: str):
    """
    Send notification to manager

    return failed messages wich down with SMTPError

    :param manager_id:
    :param manager_email:
    :param manager_key: redis_list_key of messages to manager
    :return: list[str[failed_msgs]]
    """
    messages_data = create_msgsdata_for_email(manager_id, choose_messages(manager_key))
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


@celery.task(
    bind=True,
    ignore_result=True,
    max_retries=8,
    default_retry_delay=8,
    retry_jitter=True,
    # acks_late=True,; не терять смски при worker kill. сделать pending-messages,processing-messages(lmove/blmove) в redis
    reject_on_worker_lost=True,
)
def send_notification_task(self, manager: int, manager_email: str):
    s_manager = str(manager)
    lock_key = f"{manager}_lock"
    lock_token = str(uuid.uuid4())

    if redis_broker.llen(s_manager) == 0:
        logger.info(f"Messages for {manager}  already send")
        return
    elif not redis_broker.set(lock_key, lock_token, nx=True, ex=60):
        logger.info(f"Manager {manager} is locked, retrying later")
        raise self.retry()

    try:
        fails = send_manager(manager, manager_email, s_manager)
        if fails:
            redis_broker.lpush(f"{s_manager}:retry", *fails)
            notification_retry_task.apply_async((manager, manager_email), countdown=5)
    except Exception as e:
        logger.error(repr(e), exc_info=True)
    finally:
        release_manager_lock(lock_key, lock_token)


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=8,
    retry_jitter=True,
    # acks_late=True,; не терять смски при worker kill. сделать pending-messages,processing-messages(lmove/blmove) в redis
    reject_on_worker_lost=True,
)
def notification_retry_task(self, manager: int, manager_email: str):
    manager_key = f"{manager}:retry"
    lock_key = f"{manager_key}_lock"
    lock_token = str(uuid.uuid4())

    if redis_broker.llen(manager_key) == 0:
        logger.info(f"Retries for {manager_key} already done")
        return
    elif not redis_broker.set(lock_key, lock_token, nx=True, ex=60):
        logger.info(f"Manager {manager_key} is locked, retrying later")
        raise self.retry()

    try:
        fails = send_manager(manager, manager_email, manager_key)
        if fails:
            if self.request.retries == self.max_retries - 1:
                pass
            else:
                redis_broker.lpush(manager_key, *fails)
                self.retry()
    except Exception as e:
        logger.error(f"Retry_MsgTask {repr(e)}", exc_info=True)
    finally:
        release_manager_lock(lock_key, lock_token)
