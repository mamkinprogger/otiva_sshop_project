@echo off
setlocal EnableDelayedExpansion

pushd "%~dp0"

set "COMPOSE_DEV=..\..\compose-dev.yml"
set "COMPOSE_LOAD=..\compose-load.yml"

set "REPORT_DIR=..\_reports"
if not exist %REPORT_DIR% mkdir %REPORT_DIR%

if not exist "%COMPOSE_DEV%" (
    echo compose-dev.yml not found!
    exit /b 1
)
if not exist "%COMPOSE_LOAD%" (
    echo compose-load.yml not found!
    exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set "TIMESTAMP=%%i"

set "TEST_FILE=notif-send"
set /p "TEST_FILE=Test file (%TEST_FILE%): "
set "TEST_TYPE=smoke"
set /p "TEST_TYPE=Test type (%TEST_TYPE%): "
set "TEST_PATH=..\..\otiva_sshop\chat\tests\load"
set /p "TEST_PATH=Test path (%TEST_PATH%): "
set "LOADTEST=%TEST_PATH:..\=%"

rem Remove .js if the user entered the extension
if /i "%TEST_FILE:~-3%"==".js" set "TEST_FILE=%TEST_FILE:~0,-3%"


set /p "MAKE_REPORT=Make report (not empty if true): "
set "REPORT="
if defined MAKE_REPORT (
    set "REPORT_NAME=%TEST_PATH%"
    rem Remove leading ..\ (twice)
    set "REPORT_NAME=!REPORT_NAME:..\=!"
    set "REPORT_NAME=!REPORT_NAME:..\=!"
    rem Replace backslashes with underscores
    set "REPORT_NAME=!REPORT_NAME:\=_!"
    rem Remove tests_load suffix
    set "REPORT_NAME=!REPORT_NAME:_tests_load=!"
    rem Remove trailing underscore if present
    if "!REPORT_NAME:~-1!"=="_" set "REPORT_NAME=!REPORT_NAME:~0,-1!"

    rem Create report directory
    if not exist "%REPORT_DIR%\!REPORT_NAME!" (
        mkdir "%REPORT_DIR%\!REPORT_NAME!"
    )

    set "REPORT=/reports/%TEST_FILE%_!TIMESTAMP!.html"
)

set "SCRIPT=%TEST_PATH%\scripts\test_%TEST_FILE%.bat"
set "TEST_FILE=%TEST_FILE%.js"

echo Update images...
docker compose -f %COMPOSE_DEV% -f %COMPOSE_LOAD% build

echo Removing containers...
docker compose -f %COMPOSE_DEV% -f %COMPOSE_LOAD% down 2> nul

echo Removing volumes...
docker volume rm otiva_sshop_project_redis_load_data otiva_sshop_project_pg_load_data 2> nul

echo Testing %TEST_FILE%...
call %SCRIPT%


if errorlevel 1 (
    echo Test finished with an error. Check k6 output.
)
if defined REPORT (
    if exist "..\_reports\%REPORT_NAME%\%TEST_FILE:~0,-3%_%TIMESTAMP%.html" (
        echo Report saved: ..\_reports\%REPORT_NAME%\%TEST_FILE:~0,-3%_%TIMESTAMP%.html
    ) else (
        echo Report file was not found.
    )
)

popd
endlocal
exit /b
