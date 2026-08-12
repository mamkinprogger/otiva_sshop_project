import os

from celery import Celery

from app.settings import CELERY

os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'app.settings' )

celery_client = Celery('otiva_shop')
celery_client.config_from_object(CELERY)

# загрузить все task модули из
# всех зарегистрированных django apps'ov
celery_client.autodiscover_tasks()


@celery_client.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
    return 1
