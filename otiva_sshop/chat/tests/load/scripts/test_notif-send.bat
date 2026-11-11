@echo off

echo Removing containers...
docker compose -f ..\..\..\..\..\compose-dev.yml -f ..\compose-load.yml down

echo Removing volumes...
docker volume rm otiva_sshop_project_redis_load_data otiva_sshop_project_pg_load_data


echo Start services...
docker compose -f ..\..\..\..\..\compose-dev.yml -f ..\compose-load.yml ^
    up -d ^
    --scale k6=0

if errorlevel 1 exit /b 1

echo Start testing...
docker compose -f ..\..\..\..\..\compose-dev.yml -f ..\compose-load.yml run --rm --service-ports ^
    -e "TEST_FILE=%TEST_FILE%" ^
    -e "REPORT=%REPORT%" ^
    -e "TEST_TYPE=%TEST_TYPE%" ^
    k6

docker compose -f ..\..\..\..\..\compose-dev.yml -f ..\compose-load.yml stop

exit /b %errorlevel%