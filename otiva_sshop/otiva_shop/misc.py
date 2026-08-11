import os

from otiva_shop.settings import CELERY

os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'otiva_shop.settings' )

from celery import Celery

# from otiva_shop.settings import CELERY

app = Celery('otiva_shop')
app.config_from_object(CELERY)

# загрузить все task модули из всех зарегистрированных django apps'ov
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
    return 1
