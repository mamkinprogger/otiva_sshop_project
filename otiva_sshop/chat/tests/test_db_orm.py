import pytest
from users.models import Clients

from chat.db_orm import orm_update_client_emails_history

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.database,
]


class TestUpdateClientEmailsHistory:
    def test_successful_updating(self):
        pass
