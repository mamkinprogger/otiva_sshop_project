@echo off
setlocal

pushd "%~dp0"

if not exist "..\_reports" mkdir "..\_reports"
if not exist "..\..\..\..\..\compose-dev.yml" (
    echo compose-dev.yml not found!
    exit /b 1
)
if not exist "..\compose-load.yml" (
    echo compose-load.yml not found!
    exit /b 1
)

echo Ensure that all images are updated.

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set "TIMESTAMP=%%i"

set "TEST_FILE=webhook-resp"
set /p "TEST_FILE=Test file (%TEST_FILE%): "
set "TEST_TYPE=smoke"
set /p "TEST_TYPE=Test type (%TEST_TYPE%): "

if not defined TEST_FILE set "TEST_FILE=webhook-response"
if not defined TEST_Type set "TEST_TYPE=smoke"

rem Remove .js if the user entered the extension
if /i "%TEST_FILE:~-3%"==".js" set "TEST_FILE=%TEST_FILE:~0,-3%"

set /p "MAKE_REPORT=Make report (not empty if true): "
set "REPORT="
if defined MAKE_REPORT set "REPORT=/reports/%TEST_FILE%_%TIMESTAMP%.html"

set "SCRIPT=test_%TEST_FILE%.bat"
set "TEST_FILE=%TEST_FILE%.js"

echo Update images...
rem docker compose -f ..\..\..\..\..\compose-dev.yml -f ..\compose-load.yml build

call %SCRIPT%


if errorlevel 1 (
    echo Test finished with an error. Check k6 output.
)
if defined REPORT (
    if exist "..\_reports\%TEST_FILE:~0,-3%_%TIMESTAMP%.html" (
        echo Report saved: ..\reports\%TEST_FILE:~0,-3%_%TIMESTAMP%.html
    ) else (
        echo Report file was not found.
    )
)

popd
endlocal
exit /b
