from django.contrib import admin

from users.models import Managers, Clients


class FullNameMixin:
    @staticmethod
    def fullname(first_name: str | None, last_name: str | None) -> str:
        """Create fullname from firstname and lastname"""
        first_name = first_name if first_name else "Анонимный"
        last_name = last_name or ""
        if last_name:
            return f"{first_name} {last_name}"
        return first_name


@admin.register(Managers)
class ManagersAdmin(FullNameMixin, admin.ModelAdmin):
    list_display = (
        'manager_id',
        'manager_fullname',
        'missed_calls',
        'sales',
        'message_lag',
    )
    list_editable = ['sales', "missed_calls"]
    search_fields = ["name", "manager_id", "lastname", "clients__name"]
    list_filter = ["missed_calls", "sales"]


    @admin.display(description="Имя менеджера")
    def manager_fullname(self, obj) -> str:
        return super().fullname(obj.name, obj.lastname)


    @admin.display(description="Среднее время ожидания клиента")
    def message_lag(self, obj):
        sum_time = obj.time_waiting_client
        messages = obj.received_messages

        if 0 in [sum_time, messages]:
            return "0"
        average_time_minutes = (sum_time/messages)//60
        return f"{average_time_minutes}"


@admin.register(Clients)
class ClientsAdmin(FullNameMixin, admin.ModelAdmin):
    list_display = [
        'client_id',
        'client_fullname',
        'name',
        'lastname',
        'personal_discount',
    ]
    search_fields = ["client_id", "name", "lastname", 'pinned_manager__manager_id']
    list_filter = ["name", "lastname", "personal_discount"]
    list_editable = ["name", "lastname", "personal_discount"]

    @admin.display(description="Имя клиента")
    def client_fullname(self, obj) -> str:
        return super().fullname(obj.name, obj.lastname)
