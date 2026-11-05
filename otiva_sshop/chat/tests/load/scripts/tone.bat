@echo off
setlocal

if not exist ..\reports mkdir ..\reports

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set "TIMESTAMP=%%i"

SET "TEST-FILE=webhook-response"

SET /p "TEST-FILE=Test_file(%TEST-FILE%): "
SET /p "MAKE-REPORT=Make report(not empty if true): "
set "REPORT="
if defined MAKE-REPORT set "REPORT=/reports/%TEST-FILE%_%TIMESTAMP%.html"
set "TEST-FILE=%TEST-FILE%.js"


docker run --rm --name test_one_load ^
  -e K6_WEB_DASHBOARD=true ^
  -e K6_WEB_DASHBOARD_HOST=0.0.0.0 ^
  -e K6_WEB_DASHBOARD_PORT=5665 ^
  -e K6_WEB_DASHBOARD_PERIOD=5s ^
  -e K6_WEB_DASHBOARD_EXPORT=%REPORT% ^
  -v ".\..\tests:/src:ro" ^
  -v ".\..\_reports:/reports" ^
  -p 5665:5665 ^
  grafana/k6:latest run /src/%TEST-FILE%

if errorlevel 1 echo Test finished with an error. Check k6 output.

if defined REPORT (
    if exist "..\reports" (
        echo Report saved: ..\_reports\%TEST-FILE%_%TIMESTAMP%.html
    ) else (
        echo Report file was not found.
    )
)
exit /b
endlocal
