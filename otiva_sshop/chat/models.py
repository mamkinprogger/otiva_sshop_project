from django.db import models

from app.db.mixin import TimeStampMixin
from users.models import Clients


class ClientsChatAvito(TimeStampMixin):
    chat_id = models.CharField(max_length=200, unique=True, null=False, verbose_name="Авито-Чат клиента")

    client_member = models.ForeignKey(
        to=Clients,
        on_delete=models.CASCADE,
        to_field="client_id",
    )

    class Meta:
        db_table = "client_chat_avito"
        verbose_name = "Авито-Чата клиента"
        verbose_name_plural = "Авито-Чаты клиентов"


    def __str__(self):
        return f"{self.chat_id} | {self.client_member}"
