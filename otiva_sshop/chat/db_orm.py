from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F

from chat.models import ClientsChatAvito
from users.models import Clients, ClientPermissionError, Managers


def orm_update_client_emails_history(client_id: int, prev_email: str) -> None:
    Clients.objects.filter(client_id=client_id).update(previous_email=prev_email)


async def orm_contact_info_manager_from_client(client_id: int) -> dict | None:
    """
    If a manager is already pinned to the client

    chats of clients, clients manager and clients manager email
    :return: {"manager_id": manager_of_client, "manager_email": manager_email"} | None
    """

    manager_of_client = await Clients.objects.filter(client_id=client_id). \
        values_list("pinned_manager__manager_id", "pinned_manager__email") \
        .afirst()
    if not manager_of_client:
        return None
    return {"manager_id": manager_of_client[0], "manager_email": manager_of_client[1]}


def orm_update_manager_load(manager_id: int, call: str | None, new_chat: bool) -> bool | None:
    """
    Updated manager_load if call or new_chat

    if not call and not new_chat -> don't make db-queries and RETURN None

    :returns: True if manager updated else False if manager not exists
    """
    if not new_chat and not call:
        return None

    update_fields = dict()
    if new_chat:
        update_fields["chats_count"] = F("chats_count") + 1
        update_fields["chats_count_total"] = F("chats_count_total") + 1
    if call:
        update_fields["calls"] = F("calls") + 1
        update_fields["calls_total"] = F("calls_total") + 1
        if call == 'missed':
            update_fields["missed_calls"] = F("missed_calls") + 1
            update_fields["missed_calls_total"] = F("missed_calls_total") + 1
    return bool(Managers.objects.filter(manager_id=manager_id).update(**update_fields))


def orm_get_or_create_client_from_his_msg(
        manager_id: int,
        client_id: int,
        chat_id: str,
        get_emails=True,
) -> tuple[bool, str | None, str] | tuple[bool, str]:
    """
    Checks whether the client can send messages from the passed chat -> creates ClientsChatAvito() if necessary.
    Updates the count of messages sent by the client.

    raise ClientPermissionError if client cant write to chat

    return tuple[bool[client_just_added], prev_msg of client, client_name]
    """
    client_name = "Аноним"
    prev_email = None
    just_added = False

    manager_exists = Managers.objects.filter(manager_id=manager_id).exists()
    manager_id = manager_id if manager_exists else None

    try:
        with transaction.atomic():
            client, just_added = Clients.objects.get_or_create(
                client_id=client_id,
                defaults={
                    "pinned_manager_id": manager_id,
                    "emails_count": 1
                }
            )
            ClientsChatAvito.objects.get_or_create(
                chat_id=chat_id,
                client_member_id=client_id
            )
    except IntegrityError:
        raise ClientPermissionError(
            f"Клиент {client_id} пытается получить доступ к чату который ему не принадлежит"
        ) from None

    if not just_added:
        if client.name and (name := client.name.strip()):
            client_name = name
        if client.previous_email and (email := client.previous_email.strip()):
            prev_email = email

        updated_fields: dict[str, Any] = {"emails_count": F("emails_count") + 1}
        if not client.pinned_manager_id and manager_exists:
            updated_fields["pinned_manager_id"] = manager_id
        Clients.objects.filter(client_id=client_id).update(**updated_fields)

    return (just_added, prev_email, client_name) if get_emails else (just_added, client_name)
