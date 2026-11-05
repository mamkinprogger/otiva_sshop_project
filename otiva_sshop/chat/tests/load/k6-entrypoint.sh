#!/bin/sh

if [ "$BASE_URL" = "http://web:8000" ]
then
    echo "Ждем запуск приложения..."

    while ! nc -z "web" 8000; do
      sleep 0.5
    done

    echo "Приложение запущено"
fi

exec k6 "$@"
