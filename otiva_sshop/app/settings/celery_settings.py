import sys

from kombu import Queue

from app.settings import TIME_ZONE, REDIS_BROKER, REDIS_RESULT

start_argv = sys.argv

TESTING = 'test' in start_argv
TESTING = TESTING or 'test_coverage' in start_argv or 'pytest' in sys.modules

MIN_MAIL_ID_COUNT = 50

CELERY_TASK_QUEUES = (
    Queue('chatting'),
    Queue("celery"),
    Queue("make_emails_ids")
)

CELERY_TASK_ROUTES = {
    ###chat tasks###
    'chat.tasks.send_notification_task': {
        'queue': 'chatting',
        'priority': 0,
    },
    'chat.tasks.notification_retry_task': {
        'queue': 'chatting',
        'priority': 4,
    },
    'chat.tasks.create_mail_id_task': {
        'queue': 'make_emails_ids',
    }
}


CELERY = {
    "broker_url": REDIS_BROKER,
    "task_always_eager": TESTING,
    "timezone": TIME_ZONE,
    "result_backend": REDIS_RESULT,

    "task_queues": CELERY_TASK_QUEUES,
    "task_routes": CELERY_TASK_ROUTES,
    "broker_transport_options": {
        "priority_steps": list(range(10)),
        "sep": ":",
        "queue_order_strategy": "priority",
    },

    # включить более подробные результаты
    # 'result_extended': True,
    # отображать статус "started" для задач
    "task_track_started": True,
}
