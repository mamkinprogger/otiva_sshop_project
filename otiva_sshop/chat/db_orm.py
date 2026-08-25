from django.db import IntegrityError

from chat.models import ClientsChatAvito
from users.models import Clients, ClientPermissionError


def orm_update_client_emails_history(client_id: int, emails_history: list[str]) -> None:
    Clients.objects.filter(client_id=client_id).update(emails_history=':'.join(emails_history))


async def contact_info_manager_from_client(client_id: int) -> dict | None:
    """
    If a manager is already pinned to the client

    return chats of clients, clients manager and clients manager email
    """

    manager_of_client = await Clients.objects.filter(client_id=client_id). \
        values_list("pinned_manager__manager_id", "pinned_manager__email") \
        .afirst()
    if not manager_of_client:
        return None
    return {"manager_id": manager_of_client[0], "manager_email": manager_of_client[1]}


def orm_update_manager_load(
        manager_id: int,
        client_id: int,
        chat_id: str,
        call: str | None,
        new_chat: bool,
        get_emails=True,
) -> tuple[int, list] | int:
    """
    Updating manager load

    If a new client - add to db

    If get_emails False return client_id

    return tuple[client_id, emails history of client]

    """
    try:
        client, just_added = Clients.objects. \
            select_related("pinned_manager"). \
            get_or_create(
            client_id=client_id,
            pinned_manager_id=manager_id,
        )
        ClientsChatAvito.objects.get_or_create(chat_id=chat_id, client_member_id=client_id)
        manager_data = client.pinned_manager
    except IntegrityError as e:
        if e.args[0].split("\"")[-2].split("=")[0] == "(chat_id)":
            raise ClientPermissionError(f"Клиент {client_id} пытается получить доступ к чату который ему не принадлежит") from None
        raise ClientPermissionError("Client with passed id already exists and is linked to another manager") from e

    if new_chat:
        manager_data.chats_count += 1
        manager_data.chats_count_total += 1
    if call:
        manager_data.calls += 1
        manager_data.calls_total += 1
        if call == 'missed':
            manager_data.missed_calls += 1
            manager_data.missed_calls_total += 1
    manager_data.save()

    if get_emails:
        return (client.client_id, []) if just_added else (client.client_id, client.emails_history.split(":"))
    else:
        return client_id

