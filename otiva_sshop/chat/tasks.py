import time

from otiva_shop.misc import app

@app.task
def very_long_task():
    time.sleep(60)
    return "Very long task"
