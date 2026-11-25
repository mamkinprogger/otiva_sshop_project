#!/bin/sh

echo "Ждем запуск приложения..."

while ! nc -z "web" 8000; do
  sleep 0.5
done

echo "Приложение запущено"

exec k6 "$@"
