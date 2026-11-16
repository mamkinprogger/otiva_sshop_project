#!/bin/sh

if [ "$POSTGRES_DB" = "otiva_shop-db" ] || [ "$POSTGRES_DB" = "otiva_shop-db-load" ]
then
    echo "Ждем postgres..."

    while ! nc -z "db" "$POSTGRES_PORT"; do
      sleep 0.5
    done

    echo "PostgreSQL запущен"
fi

python manage.py collectstatic --noinput

python manage.py makemigrations
python manage.py migrate

if [ -n "$K6_TEST_ENV" ]
then
  echo "Preparing K6 test data..."
  python manage.py prepare_staff_data
  echo "K6 test data prepared successfully"
fi

exec "$@"