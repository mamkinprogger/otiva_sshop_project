from django.db import models

from app.db.mixin import TimeStampMixin


class Managers(TimeStampMixin):
    """managers data"""
    manager_id = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=200, verbose_name="Имя менеджера")
    lastname = models.CharField(max_length=200, null=True, blank=True, verbose_name="Фамилия менеджера")
    phone = models.CharField(max_length=100, verbose_name="Телефон менеджера") # шифровать
    email = models.EmailField(verbose_name="email менеджера") # шифровать

    """month states"""
    sales = models.PositiveSmallIntegerField(default=0, verbose_name="Успешные продажи")
    chats = models.JSONField(default=list, null=True, blank=True, verbose_name="Закрепленные чаты за менеджером")
    calls = models.PositiveIntegerField(default=0, verbose_name="Звонки")
    missed_calls = models.PositiveIntegerField(default=0, verbose_name="Пропущенные звонки")
    time_waiting_client = models.PositiveBigIntegerField(default=0, verbose_name="Суммарное время в секундах ожидания клиента")
    received_messages = models.PositiveIntegerField(default=0, verbose_name="Полученные сообщения")


    class Meta:
        db_table = 'manager'
        verbose_name = 'Менеджера'
        verbose_name_plural = 'Менеджеры'
        ordering = ("id",)

    def __str__(self):
        return f"{self.name} - {self.manager_id}"



class Clients(TimeStampMixin):
    client_id = models.PositiveBigIntegerField(unique=True, verbose_name="ID клиента")
    name = models.CharField(max_length=200, null=True, verbose_name="Имя клиента")
    lastname = models.CharField(max_length=200, null=True, blank=True, verbose_name="Фамилия клиента")
    email = models.EmailField(null=True, blank=True, verbose_name="Email клиента") # шифровать
    phone = models.CharField(max_length=100, null=True, blank=True, verbose_name="Телефон клиента") # шифровать
    personal_discount = models.DecimalField(default=0.00, max_digits=4, decimal_places=2, verbose_name="Персональная скидка в %")

    pinned_manager = models.ForeignKey(
        to=Managers,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'client'
        verbose_name = 'Клиента'
        verbose_name_plural = 'Клиенты'
        ordering = ("id",)

    def __str__(self):
        return f"{self.name} - {self.client_id}"