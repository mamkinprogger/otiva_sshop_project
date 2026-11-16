import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from app.misc.redis_misc import sredis
from app.settings import K6_TEST_ENV, DEBUG

from users.models import Managers


class Command(BaseCommand):
    help = "Prepare staff data"

    def handle(self, *args, **options):
        if not K6_TEST_ENV and not DEBUG:
            self.stdout.write(self.style.SUCCESS(f"Cant run command outside of k6 or debug mode"))
            return

        managers_data = [
            {
                "manager_id": 11116 if K6_TEST_ENV else 11111,
                "email": "manager1@example.com" if K6_TEST_ENV else os.getenv("MANAGERS_EMAILS"),
                "phone": "+40700000001",
            },
            {
                "manager_id": 21116 if K6_TEST_ENV else 21111,
                "email": "manager2@example.com" if K6_TEST_ENV else os.getenv("MANAGERS_EMAILS"),
                "phone": "+40700000002",
            },
        ]

        # 1. Create or update managers in PostgreSQL.
        with transaction.atomic():
            managers = []
            for data in managers_data:
                manager, created = Managers.objects.update_or_create(
                    manager_id=data["manager_id"],
                    defaults={
                        "email": data["email"],
                        "phone": data["phone"],
                    },
                )

                managers.append(manager)

                action = "Created" if created else "Updated"
                self.stdout.write(
                    f"{action} manager: {manager.manager_id}"
                )

        # 2. Prepare Redis.
        for manager in managers_data:
            sredis.hset("managers", manager["manager_id"], 0)
            sredis.hset("emails_managers", manager["manager_id"], manager["email"])

        self.stdout.write(
            self.style.SUCCESS("Redis hash initialized successfully")
        )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully prepared {len(managers)} {"managers for k6" if K6_TEST_ENV else ""}")
        )

        # 2. Create Django superuser.
        User = get_user_model()

        username = "k6" if K6_TEST_ENV else "mamk"
        password = "k6" if K6_TEST_ENV else "mamk"
        email = "k6_admin@example.com"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' created")
            )
        else:
            self.stdout.write(f"Superuser '{username}' already exists")
