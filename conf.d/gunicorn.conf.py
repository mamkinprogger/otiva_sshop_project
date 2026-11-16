import multiprocessing
from app.settings import DEBUG, K6_TEST_ENV

# gunicorn app.wsgi:application -c gunicorn.conf.py

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 if not (DEBUG or K6_TEST_ENV) else 8

# worker_class = "uvicorn.workers.UvicornWorker" # app.settings.uvicorn_worker.CustomUvicornWorker
worker_class = "app.settings.uvicorn_worker.CustomUvicornWorker"

# Альтернативы worker_c1ass:
# - "uvicorn.workers.UvicornH11Worker” - использует h11 (pure Python HTTP)
# - “sync" - для синхронных WSGI приложений (НЕ для FastAPI!)
# - "gevent" - для gevent-based приложений
# - "eventlet" - для eventlet-based приложений

# через какое время будет убит воркер, то есть какое допустимое время gunicorn видит сколько процесс не отвечает(работает(актуально для синхронного, тк асинхронный по сути ему ответит))
# time > duration_longest_request
# должно быть синхронизировано с nginx timeout, если nginx < gunicorn, то все будет убиваться
#
timeout = 30

# можно также включить max_requests если ловим утечку памяти
# можно также указать максимальные размеры заголовков, чтобы защитится от Dos, синхронизируем с nginx
# для django можно написать свой класс uvicorn воркера, чтобы выключить lifespan в асинхронном варианте(а в каком же еще если мы uvicorn запускаем)

accesslog = "-"

loglevel = "info" if DEBUG else "warning"
