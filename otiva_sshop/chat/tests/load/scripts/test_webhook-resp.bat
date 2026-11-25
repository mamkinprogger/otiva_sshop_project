@echo off

echo Start services...
docker compose -f %COMPOSE_DEV% -f %COMPOSE_LOAD% ^
    up -d ^
    --scale celery=0 ^
    --scale celery-make-ids=0 ^
    --scale celery-beat=0 ^
    --scale flower=0 ^
    --scale k6=0

if errorlevel 1 exit /b 1

echo Start testing...
docker compose -f %COMPOSE_DEV% -f %COMPOSE_LOAD% run --rm --service-ports ^
    -e "TEST_FILE=%TEST_FILE%" ^
    -e "REPORT=%REPORT%" ^
    -e "TEST_TYPE=%TEST_TYPE%" ^
    k6

docker compose -f %COMPOSE_DEV% -f %COMPOSE_LOAD% stop

exit /b %errorlevel%