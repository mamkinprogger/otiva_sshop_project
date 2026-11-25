@echo off
setlocal EnableDelayedExpansion

pushd "%~dp0"

set "COMPOSE_DEV=..\..\compose-dev.yml"
set "COMPOSE_LOAD=..\compose-load.yml"

set "REPORT_DIR=..\_reports"
set "PATHS_FILE=paths_scripts.txt"

if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"

if not exist "%COMPOSE_DEV%" (
    echo compose-dev.yml not found!
    popd
    exit /b 1
)
if not exist "%COMPOSE_LOAD%" (
    echo compose-load.yml not found!
    popd
    exit /b 1
)
if not exist "%PATHS_FILE%" (
    echo paths_scripts.txt not found!
    popd
    exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set "TIMESTAMP=%%i"

set "TEST_TYPE=smoke"
set /p "TEST_TYPE=Test type (%TEST_TYPE%): "
set "MAKE_REPORT="
set /p "MAKE_REPORT=Make report (not empty if true): "
set "REPORT="
set "TEST_FILE="
set "REPORT_NAME="
set "LOADTEST="
set /a TOTAL_TESTS=0
set /a FAILED_TESTS=0



echo.
echo ==========================================
echo Preparing Docker environment...
echo ==========================================
setlocal

set "REPORT=1"
set "TEST_FILE=1"
set "REPORT_NAME=1"
set "LOADTEST=1"

docker compose -f "%COMPOSE_DEV%" -f "%COMPOSE_LOAD%" build

if errorlevel 1 (
    endlocal
    exit /b 1
)

endlocal



echo.
echo ==========================================
echo Starting all tests...
echo ==========================================

for /f "usebackq tokens=* delims=" %%P in ("%PATHS_FILE%") do (
    set "TEST_PATH=%%P"
    set "LOADTEST=!TEST_PATH:..\=!"

    if defined TEST_PATH (
        echo.
        echo ==========================================
        echo Test directory: !TEST_PATH!
        echo ==========================================

        set "SCRIPT_DIR=!TEST_PATH!\scripts"
        if not exist "!SCRIPT_DIR!" (
            echo Scripts directory not found: !SCRIPT_DIR!
        ) else (
            for %%F in ("!SCRIPT_DIR!\*.bat") do (
                if exist "%%~fF" (
                    set /a TOTAL_TESTS+=1
                    set "SCRIPT=%%~fF"
                    set "TEST_FILE=%%~nF"
                    rem Remove test_ prefix
                    set "TEST_NAME=!TEST_FILE:test_=!"
                    set "REPORT="
                    set "REPORT_NAME="

                    if defined MAKE_REPORT (
                        set "REPORT_NAME=!TEST_PATH!"
                        rem Remove leading ..\
                        set "REPORT_NAME=!REPORT_NAME:..\=!"
                        set "REPORT_NAME=!REPORT_NAME:..\=!"
                        rem Replace backslashes with underscores
                        set "REPORT_NAME=!REPORT_NAME:\=_!"
                        rem Remove tests_load suffix
                        set "REPORT_NAME=!REPORT_NAME:_tests_load=!"

                        if "!REPORT_NAME:~-1!"=="_" set "REPORT_NAME=!REPORT_NAME:~0,-1!"
                        if not exist "%REPORT_DIR%\!REPORT_NAME!" mkdir "%REPORT_DIR%\!REPORT_NAME!"
                        set "REPORT=/reports/!TEST_NAME!_!TIMESTAMP!.html"
                    )

                    echo.
                    echo Removing containers...
                    docker compose -f "%COMPOSE_DEV%" -f "%COMPOSE_LOAD%" down 2>nul
                    echo Removing volumes...
                    docker volume rm otiva_sshop_project_redis_load_data otiva_sshop_project_pg_load_data 2>nul
                    echo ------------------------------------------
                    echo Running: !TEST_FILE!
                    echo Path: !TEST_PATH!
                    echo ------------------------------------------

                    set "TEST_FILE=!TEST_NAME!.js"
                    call "!SCRIPT!"

                    if errorlevel 1 (
                        echo.
                        echo [ERROR] Test !TEST_NAME! failed.
                        set /a FAILED_TESTS+=1
                    ) else (
                        echo.
                        echo [SUCCESS] Test !TEST_NAME! completed.
                    )

                    if defined REPORT (
                        if exist "%REPORT_DIR%\!REPORT_NAME!\!TEST_NAME!_!TIMESTAMP!.html" (
                            echo Report saved: %REPORT_DIR%\!REPORT_NAME!\!TEST_NAME!_!TIMESTAMP!.html
                        ) else (
                            echo Report file was not found.
                        )
                    )
                )
            )
        )
    )
)

echo.
echo ==========================================
echo TEST EXECUTION SUMMARY
echo ==========================================

echo Total tests:  !TOTAL_TESTS!
echo Failed tests: !FAILED_TESTS!
echo Successful:   !TOTAL_TESTS! - !FAILED_TESTS!

popd
endlocal
exit /b 0
