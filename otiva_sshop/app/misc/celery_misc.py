import os
from datetime import timedelta

from celery import Celery

from app.settings import CELERY

os.environ.setdefault('DJANGO_SETTINGS_MODULE','app.settings')

celery = Celery('otiva_shop')
celery.config_from_object(CELERY)

celery.autodiscover_tasks()
