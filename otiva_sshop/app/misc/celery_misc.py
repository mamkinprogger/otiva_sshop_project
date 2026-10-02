import os
from datetime import timedelta

from celery import Celery

from app.settings import CELERY

os.environ.setdefault('DJANGO_SETTINGS_MODULE','app.settings')

celery = Celery('otiva_shop')
celery.config_from_object(CELERY)

celery.autodiscover_tasks()

celery.conf.beat_schedule = {
    "creating_emails_ids": {
        'task': "chat.tasks.create_mail_id_task",
        'schedule': timedelta(seconds=2),
    }
}
