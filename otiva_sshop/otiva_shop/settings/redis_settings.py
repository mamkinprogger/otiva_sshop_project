import os

from otiva_shop.settings import read_secret, DOCKER_START_APP

REDIS_HOST = 'redis' if DOCKER_START_APP else 'localhost'
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = read_secret('redis_password') or os.getenv('REDIS_PASSWORD')

REDIS_URL = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}'

REDIS_CLIENT = REDIS_URL + '/0'
REDIS_BROKER = REDIS_URL + '/1'
REDIS_RESULT = REDIS_URL + '/2'

