import time

from app.misc.celery import celery_client

@celery_client.task
def very_long_task():
    time.sleep(60)
    return "Very long task"
