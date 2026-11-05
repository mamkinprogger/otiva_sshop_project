import pytest

from chat.models import ClientsChatAvito
from users.models import Clients, Managers, ClientPermissionError

from chat.db_orm import orm_update_client_emails_history, orm_contact_info_manager_from_client, \
    orm_get_or_create_client_from_his_msg, orm_update_manager_load

pytestmark = [
    pytest.mark.database,
    pytest.mark.slow,
]

@pytest.fixture
def db_client_factory():
    def create_client(**kwargs) -> Clients:
        defaults = {
            "previous_email": "",
        }
        defaults.update(kwargs)
        return Clients.objects.create(**defaults)
    return create_client

@pytest.fixture
def adb_client_factory():
    async def create_client(**kwargs) -> Clients:
        defaults = {
            "previous_email": "",
        }
        defaults.update(kwargs)
        return await Clients.objects.acreate(**defaults)
    return create_client

@pytest.fixture
def db_manager_factory():
    def create_manager(**kwargs) -> Managers:
        defaults = {
            "name": 'managerik',
            "phone": "91001",
            "email": "aa@a.ru",
        }
        defaults.update(kwargs)
        return Managers.objects.create(**defaults)
    return create_manager

@pytest.fixture
def adb_manager_factory():
    async def create_manager(**kwargs) -> Managers:
        defaults = {
            "name": 'managerik',
            "phone": "91001",
            "email": "aa@a.ru",
        }
        defaults.update(kwargs)
        return await Managers.objects.acreate(**defaults)
    return create_manager


@pytest.mark.django_db
class TestUpdateClientEmailsHistory:
    def test_successful_updating(self, db_client_factory):
        client = db_client_factory(client_id=1)
        orm_update_client_emails_history(client_id=client.client_id, prev_email="<1234>")
        client.refresh_from_db()

        assert client.previous_email == "<1234>"

    def test_empty_updating(self, db_client_factory):
        client = db_client_factory(client_id=1)
        orm_update_client_emails_history(client_id=client.client_id, prev_email="")
        client.refresh_from_db()

        assert client.previous_email == ""


@pytest.mark.django_db(transaction=True)
class TestContactInfoManagersFromClient:
    async def test_client_have_manager(self, adb_client_factory, adb_manager_factory):
        manager = await adb_manager_factory(manager_id=23)
        client = await adb_client_factory(client_id=1, pinned_manager_id=manager.manager_id)

        result = await orm_contact_info_manager_from_client(client_id=client.client_id)

        assert isinstance(result, dict)
        assert result == {
            "manager_id": manager.manager_id,
            "manager_email": manager.email,
        }

    async def test_client_dont_have_manager(self, adb_client_factory):
        client = await adb_client_factory(client_id=1)

        result = await orm_contact_info_manager_from_client(client_id=client.client_id)

        assert isinstance(result, dict)
        assert result == {
            "manager_id": None,
            "manager_email": None,
        }

    async def test_no_client(self):
        result = await orm_contact_info_manager_from_client(client_id=1)
        assert result is None


@pytest.mark.django_db
class TestUpdateManagerLoad:
    def test_successful_updating(self, db_manager_factory):
        manager = db_manager_factory(manager_id=23)

        result = orm_update_manager_load(manager_id=manager.manager_id, new_chat=True, call="missed")

        manager.refresh_from_db()
        assert manager.chats_count == 1
        assert manager.chats_count_total == 1
        assert manager.calls == 1
        assert manager.calls_total == 1
        assert manager.missed_calls == 1
        assert manager.missed_calls_total == 1
        assert result is True

    def test_update_chats_count(self, db_manager_factory):
        manager = db_manager_factory(manager_id=23)

        result = orm_update_manager_load(manager_id=manager.manager_id, new_chat=True, call=None)

        manager.refresh_from_db()
        assert manager.chats_count == 1
        assert manager.chats_count_total == 1
        assert manager.calls_total == 0
        assert manager.missed_calls_total == 0
        assert result is True

    def test_update_calls_count(self, db_manager_factory):
        manager = db_manager_factory(manager_id=23)

        result = orm_update_manager_load(manager_id=manager.manager_id, new_chat=False, call="not_missed")

        manager.refresh_from_db()
        assert manager.chats_count_total == 0
        assert manager.calls == 1
        assert manager.calls_total == 1
        assert manager.missed_calls_total == 0
        assert result is True

    def test_update_missed_calls_count(self, db_manager_factory):
        manager = db_manager_factory(manager_id=23)

        result = orm_update_manager_load(manager_id=manager.manager_id, new_chat=False, call="missed")

        manager.refresh_from_db()
        assert manager.chats_count_total == 0
        assert manager.calls == 1
        assert manager.calls_total == 1
        assert manager.missed_calls == 1
        assert manager.missed_calls_total == 1
        assert result is True

    def test_not_updated(self):
        result = orm_update_manager_load(manager_id=23, new_chat=False, call=None)
        assert result is None


@pytest.mark.django_db
class TestGetOrCreateClientFromHisMsg:
    def test_successful_creating_client(self, db_manager_factory):
        manager = db_manager_factory(manager_id=23)
        client_id = 1
        chat_id = "ABC-chat"

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client_id,
            chat_id=chat_id,
            get_emails=False
        )

        client = Clients.objects.filter(client_id=client_id).select_related("pinned_manager").get()
        assert client.pinned_manager == manager
        assert client.emails_count == 1
        assert client.previous_email == ""

        chat = ClientsChatAvito.objects.filter(chat_id=chat_id, client_member_id=client_id).get()
        assert chat.chat_id == chat_id
        assert chat.client_member_id == client_id

        assert result == {
            "client_added": True,
            "client_name": "Аноним",
            "chat_added": True,
            "increase_manager_load": True,
        }

    def test_client_exists_but_just_written_in_chat(self, db_manager_factory, db_client_factory):
        manager = db_manager_factory(manager_id=23)
        client = db_client_factory(client_id=1, name="Виталий")
        chat_id = "ABC-chat"

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client.client_id,
            chat_id=chat_id,
            get_emails=False
        )
        client = Clients.objects.filter(client_id=client.client_id).select_related("pinned_manager").get()
        assert client.pinned_manager == manager
        assert client.emails_count == 1

        chat = ClientsChatAvito.objects.filter(chat_id=chat_id, client_member_id=client.client_id).get()
        assert chat.chat_id == chat_id
        assert chat.client_member_id == client.client_id
        assert result == {
            "client_added": False,
            "client_name": "Виталий",
            "chat_added": True,
            "increase_manager_load": True,
        }

    def test_client_open_second_chat(self, db_client_factory, db_manager_factory):
        manager = db_manager_factory(manager_id=23)
        client_id = 223
        chat_id_1 = "ABC-chat"

        orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client_id,
            chat_id=chat_id_1,
            get_emails=False
        )
        chat_id_2 = "ABC-chat2"
        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client_id,
            chat_id=chat_id_2,
            get_emails=False
        )

        client_chats = ClientsChatAvito.objects.filter(client_member__client_id=client_id).all()
        assert len(client_chats) == 2
        for chat in client_chats:
            assert chat.chat_id in [chat_id_1, chat_id_2]
            assert chat.client_member_id == client_id
        assert result == {
            "client_added": False,
            "client_name": "Аноним",
            "chat_added": True,
            "increase_manager_load": False,
        }

    def test_client_chatted_before_his_prev_email_updated(self, db_manager_factory, db_client_factory):
        manager = db_manager_factory(manager_id=23)
        client = db_client_factory(client_id=1, name="Виталий")
        chat_id = "ABC-chat"

        orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client.client_id,
            chat_id=chat_id,
            get_emails=False
        )
        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client.client_id,
            chat_id=chat_id,
            get_emails=False
        )

        client_chats = ClientsChatAvito.objects.filter(client_member__client_id=client.client_id).all()
        assert len(client_chats) == 1
        assert client_chats[0].chat_id == chat_id
        assert client_chats[0].client_member_id == client.client_id
        assert result == {
            "client_added": False,
            "client_name": "Виталий",
            "chat_added": False,
            "increase_manager_load": False,
        }

    def test_new_client_chatting_in_foreign_chat(self, db_client_factory, db_manager_factory):
        manager = db_manager_factory(manager_id=23)
        client1 = db_client_factory(client_id=1, name="Виталий")
        chat_id = "ABC-chat"
        ClientsChatAvito.objects.create(chat_id=chat_id, client_member_id=client1.client_id)

        with pytest.raises(ClientPermissionError, match=r"не принадлежит"):
            orm_get_or_create_client_from_his_msg(
                manager_id=manager.manager_id,
                client_id=34,
                chat_id=chat_id,
                get_emails=False
            )

        bad_client = Clients.objects.filter(client_id=34).first()
        assert bad_client is None

    def test_old_client_chatting_in_foreign_chat(self, db_client_factory, db_manager_factory):
        manager = db_manager_factory(manager_id=23)
        client1 = db_client_factory(client_id=1, name="Виталий")
        chat_id = "ABC-chat"
        ClientsChatAvito.objects.create(chat_id=chat_id, client_member_id=client1.client_id)

        client2 = db_client_factory(client_id=2, name="Геннадий")

        with pytest.raises(ClientPermissionError, match=r"не принадлежит"):
            orm_get_or_create_client_from_his_msg(
                manager_id=manager.manager_id,
                client_id=client2.client_id,
                chat_id=chat_id,
                get_emails=False
            )

    def test_manger_deleted_but_msg_from_old_client_already_in_processing_with_old_manager_id(self, db_client_factory):
        client = db_client_factory(client_id=1, name="Виталий")
        manager_id = 4

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager_id,
            client_id=client.client_id,
            chat_id="chat_id123",
            get_emails=False
        )

        client.refresh_from_db()
        assert client.pinned_manager_id is None
        assert client.emails_count == 1
        assert result == {
            "client_added": False,
            "client_name": "Виталий",
            "chat_added": True,
            "increase_manager_load": False,
        }

    def test_manger_deleted_but_msg_from_new_client_already_in_processing_with_old_manager_id(self, db_client_factory):
        client_id = 1
        manager_id = 4

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager_id,
            client_id=client_id,
            chat_id="chat_id123",
            get_emails=False
        )

        client = Clients.objects.filter(client_id=client_id).get()
        assert client.pinned_manager_id is None
        assert client.emails_count == 1
        assert result == {
            "client_added": True,
            "client_name": "Аноним",
            "chat_added": True,
            "increase_manager_load": False,
        }

    def test_get_emails_new_client(self, db_manager_factory):
        manager = db_manager_factory(manager_id=13)
        client_id = 1
        chat_id = "ABC-chat"

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client_id,
            chat_id=chat_id,
        )

        client = Clients.objects.filter(client_id=client_id).get()
        assert client.emails_count == 1
        assert client.previous_email == ""
        assert result == {
            "client_added": True,
            "client_name": "Аноним",
            "prev_email": None,
            "chat_added": True,
            "increase_manager_load": True,
        }

    def test_get_emails_old_client(self, db_manager_factory, db_client_factory):
        manager = db_manager_factory(manager_id=13)
        client = db_client_factory(client_id=1, name="Виталий")
        chat_id = "ABC-chat"

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client.client_id,
            chat_id=chat_id,
        )

        client = Clients.objects.filter(client_id=client.client_id).get()
        assert client.emails_count == 1
        assert client.previous_email == ""
        assert result == {
            "client_added": False,
            "client_name": "Виталий",
            "prev_email": None,
            "chat_added": True,
            "increase_manager_load": True,
        }

    def test_get_emails_already_chatted(self, db_manager_factory, db_client_factory):
        manager = db_manager_factory(manager_id=13)
        prev_emails = "<123.123>"
        client = db_client_factory(client_id=1, name="Виталий", previous_email=prev_emails)
        chat_id = "ABC-chat"

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client.client_id,
            chat_id=chat_id,
        )

        client = Clients.objects.filter(client_id=client.client_id).get()
        assert client.emails_count == 1
        assert client.previous_email == prev_emails
        assert result == {
            "client_added": False,
            "client_name": "Виталий",
            "prev_email": prev_emails,
            "chat_added": True,
            "increase_manager_load": True,
        }

    def test_increase_message_count(self, db_manager_factory):
        manager = db_manager_factory(manager_id=13)
        client_id = 1
        skipped_msgs = 3
        chat_id = "ABC-chat"

        result = orm_get_or_create_client_from_his_msg(
            manager_id=manager.manager_id,
            client_id=client_id,
            chat_id=chat_id,
            increase_count_msgs=skipped_msgs,
            get_emails=False
        )

        client = Clients.objects.filter(client_id=client_id).get()
        assert client.emails_count == 4
        assert client.previous_email == ""
        assert result == {
            "client_added": True,
            "client_name": "Аноним",
            "chat_added": True,
            "increase_manager_load": True,
        }
