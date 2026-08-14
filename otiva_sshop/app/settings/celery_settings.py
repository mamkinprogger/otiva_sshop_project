import sys

from app.settings import TIME_ZONE, REDIS_BROKER, REDIS_RESULT

start_argv = sys.argv

TESTING = 'test' in start_argv
TESTING = TESTING or 'test_coverage' in start_argv or 'pytest' in sys.modules


CELERY = {
    "broker_url": REDIS_BROKER,
    "task_always_eager": TESTING,
    "timezone": TIME_ZONE,
    "result_backend": REDIS_RESULT,
    # включить более подробные результаты
    # 'result_extended': True,
    # отображать статус "started" для задач
    "task_track_started": True,
}
