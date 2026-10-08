import asyncio
import json
import logging

from django.http import HttpResponse, Http404, HttpRequest
from django.views.decorators.csrf import csrf_exempt

from app.misc.redis_misc import redis, aredis_broker
from app.settings import AVITO_STORE_ID
from chat.db_orm import orm_contact_info_manager_from_client
from chat.tasks import send_notification_task
from chat.utils import MessageFromWebhook, MessageFieldsException

logger = logging.getLogger("chat_logger")


class ClientMessageError(RuntimeError):
    pass


async def assign_manager(
        *,
        manager_id: int = None,
        manager_email: str = None,
        managers_load: dict[bytes, bytes] = None,
) -> tuple[bytes, bytes]:
    """
    Selects a manager based on his workload.

    -Pass manager_id and manager_email if they are known

    -Pass manager_load if there is no information about the manager

    """
    if manager_id and not manager_email:
        raise RuntimeError("Cannot pass manager_id without manager_email")
    if not managers_load and not manager_id:
        raise RuntimeError("Managers load not passed")

    if manager_id:
        target_manager = str(manager_id).encode()
        manager_email = manager_email.encode()
    else:
        target_manager = min(managers_load, key=lambda x: int(managers_load[x]))
        manager_email = await redis.hget("emails_managers", target_manager)

    return target_manager, manager_email


async def manager_response_lag(msg: MessageFromWebhook):
    """Written the time it takes to wait for a response from manager"""
    cached_chat = await redis.get(msg.chat_id)
    if not cached_chat:
        return
    manager, received_time = map(int, cached_chat.split(b":"))
    waiting_time = abs(msg.sending_time - received_time)//60 if received_time else 0

    async with redis.pipeline(transaction=True) as pipe:
        await pipe.set(msg.chat_id, f"{manager}:0", ex=60 * 60 * 24 * 3)
        if waiting_time:
            await pipe.lpush(f"{manager}:response_lag", waiting_time)
        await pipe.execute()

async def get_client_creating(pinned_manager: bytes | None, chat_id: str) -> bool:
    if not pinned_manager:
        return False

    pend = pinned_manager
    process = pinned_manager + ":processing".encode()

    async with aredis_broker.pipeline() as pipe:
        await pipe.lrange(pend, 0, -1)
        await pipe.lrange(process, 0, -1)
        res = await pipe.execute()

    pending, processing = res
    unpacker = MessageFromWebhook()

    for msg_entity in pending+processing:
        *_, queued_msg = msg_entity.partition(b";")
        if unpacker.unpack_str_msg(queued_msg.decode())["chat_id"] == chat_id:
            return True
    return False


async def identify_manager(msg: MessageFromWebhook, managers: dict[bytes, bytes]):
    """Send email to the manager assigned to the client who sent the message"""
    pinned_manager, client = await asyncio.gather(
        redis.get(msg.chat_id),
        orm_contact_info_manager_from_client(msg.client_id)
    )
    client_creating = await get_client_creating(
        pinned_manager.split(b":")[0] if pinned_manager else None,
        msg.chat_id
    )

    if (pinned_manager and not client) and not client_creating:
        raise ClientMessageError(f"Chat {msg.chat_id} with client is open, but the client does not exist")

    if pinned_manager:
        if (client and client["manager_id"] is None) and not client_creating:
            raise ClientMessageError(f"A client without a manager cannot write to an existing chat.")

        pinned_manager, received_time = pinned_manager.split(b":")
        target_manager, manager_email = await assign_manager(**client, managers_load=managers) if client else \
                                        await assign_manager(managers_load=managers)
        received_time = received_time if int(received_time) else str(msg.sending_time).encode()
        new_chat = False
        if target_manager != pinned_manager:
            if client:
                logger.error("Менеджер активного чата в redis != менеджеру client")
                raise ClientMessageError("The manager assigned to the chat != the client's manager")
            target_manager = pinned_manager
    else:
        target_manager, manager_email = await assign_manager(**client, managers_load=managers) if client else \
                                        await assign_manager(managers_load=managers)
        received_time = str(msg.sending_time).encode()
        new_chat = True if not client or not client["manager_id"] else False

    str_msg = msg.create_str()
    msg_to_queue = f"{new_chat=};{str_msg}"
    await aredis_broker.lpush(target_manager, msg_to_queue)

    send_notification_task.delay(int(target_manager), manager_email.decode())

    async with redis.pipeline(transaction=True) as pipe:
        if new_chat:
            await pipe.hset("managers", target_manager, int(managers[target_manager]) + 1)
        await pipe.set(msg.chat_id, target_manager+b":"+received_time, ex=60 * 60 * 24 * 3)
        await pipe.execute()


@csrf_exempt
async def webhook(request: HttpRequest):
    """
    Receives a message from the API
    """
    if request.method != "POST":
        raise Http404()

    try:
        message_data = json.loads(request.body)
        if message_data["payload"]["type"] != "message" or not message_data["payload"]["value"]:
            return HttpResponse()
        managers = await redis.hgetall("managers")
        message = MessageFromWebhook(message_data["payload"]["value"])
        sender = str(message.client_id).encode()

        if sender in managers or sender == str(AVITO_STORE_ID).encode():
            await manager_response_lag(message)
        else:
            await identify_manager(message, managers)

    except MessageFieldsException as e:
        logger.error(f"Не удалось обработать сообщение: {e}")
    except ClientMessageError as e:
        if "!=" not in e.args[0]:
            logger.warning(f"Нелогичная ошибка: {repr(e)}")
    except (KeyError, TypeError) as e:
        logger.error(f"Не удалось положить сообщение от webhook в очередь {repr(e)}")
        logger.error(f"\nОбъект сообщения\n"
                       f"{request.body}")
    except Exception as e:
        logger.error(
            f"Не удалось положить сообщение от webhook в очередь Непредвиденная ошибка: {e}",
            exc_info=True
        )
    return HttpResponse()
