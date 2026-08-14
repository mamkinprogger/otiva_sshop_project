import os

from celery import Celery

from app.settings import CELERY

os.environ.setdefault('DJANGO_SETTINGS_MODULE','app.settings')

celery_client = Celery('otiva_shop')
celery_client.config_from_object(CELERY)

celery_client.autodiscover_tasks()

