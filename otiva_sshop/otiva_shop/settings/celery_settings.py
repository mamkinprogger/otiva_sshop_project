import sys

from otiva_shop.settings import TIME_ZONE

TESTING = 'test' in sys.argv
TESTING = TESTING or 'test_coverage' in sys.argv or 'pytest' in sys.modules


CELERY = {
    "broker_url": "redis://localhost:6379/1",
    # синхронное выполнение задачи при тестировании
    "task_always_eager": TESTING,
    # временная зона для планировщика
    "timezone": TIME_ZONE,
    "result_backend": "django-db",
    # включить более подробные результаты
    'result_extended': True,
    # отображать статус "started" для задач
    "task_track_started": True,
}
