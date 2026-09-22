from django.db import models

from app.db.mixin import TimeStampMixin

class ClientPermissionError(RuntimeError):
    pass

class Managers(TimeStampMixin):
    """managers data"""
    manager_id = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=200, verbose_name="Имя менеджера")
    lastname = models.CharField(max_length=200, null=True, blank=True, verbose_name="Фамилия менеджера")
    phone = models.CharField(max_length=100, verbose_name="Телефон менеджера") # шифровать
    email = models.EmailField(verbose_name="email менеджера") # шифровать

    """month states"""
    sales = models.PositiveSmallIntegerField(default=0, verbose_name="Успешные продажи")
    chats_count = models.PositiveSmallIntegerField(default=0, verbose_name="Количество чатов за этот месяц")
    calls = models.PositiveSmallIntegerField(default=0, verbose_name="Звонки")
    missed_calls = models.PositiveSmallIntegerField(default=0, verbose_name="Пропущенные звонки")
    time_waiting_client = models.PositiveIntegerField(default=0, verbose_name="Суммарное время в минутах ожидания клиента")
    count_time_waiting_client = models.PositiveIntegerField(default=1, verbose_name="count_time_waiting_client")

    """total states"""
    sales_total = models.PositiveIntegerField(default=0, verbose_name="Всего успешных продаж")
    calls_total = models.PositiveIntegerField(default=0, verbose_name="Звонков всего")
    missed_calls_total = models.PositiveIntegerField(default=0, verbose_name="Пропущенные звонки")
    chats_count_total = models.PositiveIntegerField(default=0, verbose_name="Количество чатов всего")


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

    previous_email = models.CharField(default='', max_length=100, blank=True, verbose_name="id предыдущего письма-уведомления по клиенту")
    emails_count = models.PositiveSmallIntegerField(default=0, verbose_name="Количество отправленных клиентом сообщений")

    pinned_manager = models.ForeignKey(
        to=Managers,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field='manager_id',
    )

    class Meta:
        db_table = 'client'
        verbose_name = 'Клиента'
        verbose_name_plural = 'Клиенты'
        ordering = ("id",)

    def __str__(self):
        return f"{self.name} - {self.client_id}"