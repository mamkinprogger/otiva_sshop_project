#!/bin/sh

if [ "$POSTGRES_DB" = "otiva_shop-db" ]
then
    echo "Ждем postgres..."

    while ! nc -z "db" $POSTGRES_PORT; do
      sleep 0.5
    done

    echo "PostgreSQL запущен"
fi

python manage.py collectstatic --noinput

python manage.py makemigrations
python manage.py migrate

exec "$@"