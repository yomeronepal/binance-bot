@echo off
REM Monte Carlo Simulation Test Script (Windows)
REM This script tests the Monte Carlo simulation feature end-to-end

setlocal enabledelayedexpansion

echo ========================================
echo Monte Carlo Simulation Test
echo ========================================
echo.

REM Configuration
set API_URL=http://localhost:8000
set TOKEN_FILE=%TEMP%\mc_token.txt
set RESPONSE_FILE=%TEMP%\mc_response.json

REM Step 1: Generate JWT Token
echo [1/5] Generating JWT token...
docker-compose exec -T backend python manage.py shell -c "from django.contrib.auth import get_user_model; from rest_framework_simplejwt.tokens import RefreshToken; User = get_user_model(); user = User.objects.first(); refresh = RefreshToken.for_user(user); print(str(refresh.access_token))" 2>nul | findstr /v "Traceback" > %TOKEN_FILE%

set /p TOKEN=<%TOKEN_FILE%

if "%TOKEN%"=="" (
    echo [ERROR] Failed to generate token
    exit /b 1
)
echo [OK] Token generated
echo.

REM Step 2: Create Monte Carlo Simulation
echo [2/5] Creating Monte Carlo simulation...

REM Read JSON file content
set JSON_FILE=test_montecarlo.json

curl -s -X POST "%API_URL%/api/montecarlo/" ^
  -H "Authorization: Bearer %TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d @%JSON_FILE% > %RESPONSE_FILE%

REM Extract ID from JSON response
for /f "tokens=2 delims=:," %%a in ('type %RESPONSE_FILE% ^| findstr /r "\"id\":[0-9]"') do set SIMULATION_ID=%%a
set SIMULATION_ID=%SIMULATION_ID: =%

if "%SIMULATION_ID%"=="" (
    echo [ERROR] Failed to create Monte Carlo simulation
    type %RESPONSE_FILE%
    exit /b 1
)

echo [OK] Monte Carlo simulation created (ID: %SIMULATION_ID%)
echo.

REM Step 3: Monitor Execution
echo [3/5] Monitoring execution...
echo This may take 1-5 minutes depending on number of simulations...
echo.

set MAX_WAIT=600
set WAIT_TIME=0
set STATUS=PENDING

:MONITOR_LOOP
if %WAIT_TIME% GEQ %MAX_WAIT% goto TIMEOUT
if "%STATUS%"=="COMPLETED" goto COMPLETED
if "%STATUS%"=="FAILED" goto FAILED

timeout /t 5 /nobreak >nul
set /a WAIT_TIME+=5

curl -s "%API_URL%/api/montecarlo/%SIMULATION_ID%/" ^
  -H "Authorization: Bearer %TOKEN%" > %RESPONSE_FILE%

REM Extract status and progress from JSON
for /f "tokens=2 delims=:," %%a in ('type %RESPONSE_FILE% ^| findstr "\"status\""') do (
    set STATUS=%%a
    set STATUS=!STATUS:"=!
    set STATUS=!STATUS: =!
)

for /f "tokens=2 delims=:," %%a in ('type %RESPONSE_FILE% ^| findstr "\"progress_percentage\""') do (
    set PROGRESS=%%a
    set PROGRESS=!PROGRESS: =!
)

for /f "tokens=2 delims=:," %%a in ('type %RESPONSE_FILE% ^| findstr "\"completed_simulations\""') do (
    set COMPLETED=%%a
    set COMPLETED=!COMPLETED: =!
)

for /f "tokens=2 delims=:," %%a in ('type %RESPONSE_FILE% ^| findstr "\"num_simulations\""') do (
    set TOTAL=%%a
    set TOTAL=!TOTAL: =!
)

echo Status: %STATUS% ^| Progress: !COMPLETED!/!TOTAL! (!PROGRESS!%%) ^| Time: %WAIT_TIME%s
goto MONITOR_LOOP

:TIMEOUT
echo [WARNING] Timeout reached
echo Check progress at: %API_URL%/api/montecarlo/%SIMULATION_ID%/
goto RESULTS

:FAILED
echo [ERROR] Monte Carlo simulation failed
type %RESPONSE_FILE% | findstr "error_message"
exit /b 1

:COMPLETED
echo [OK] Monte Carlo simulation completed!
echo.

:RESULTS
REM Step 4: Get Results
echo [4/5] Fetching results...

curl -s "%API_URL%/api/montecarlo/%SIMULATION_ID%/" ^
  -H "Authorization: Bearer %TOKEN%" > %RESPONSE_FILE%

echo =======================================
echo      MONTE CARLO RESULTS
echo =======================================
type %RESPONSE_FILE% | python -m json.tool 2>nul | findstr /i "\"id\" \"name\" \"status\" \"mean_return\" \"probability_of_profit\" \"robustness_score\" \"is_statistically_robust\""
echo =======================================
echo.

REM Step 5: Get Best/Worst Runs
echo [5/5] Fetching best/worst runs...

curl -s "%API_URL%/api/montecarlo/%SIMULATION_ID%/best_worst_runs/?n=5" ^
  -H "Authorization: Bearer %TOKEN%" | python -m json.tool 2>nul | more

echo.
echo =======================================
echo Test completed!
echo =======================================
echo.
echo View in browser:
echo   Summary:       %API_URL%/api/montecarlo/%SIMULATION_ID%/summary/
echo   All Runs:      %API_URL%/api/montecarlo/%SIMULATION_ID%/runs/
echo   Distributions: %API_URL%/api/montecarlo/%SIMULATION_ID%/distributions/
echo   Admin:         %API_URL%/admin/signals/montecarlosimulation/%SIMULATION_ID%/change/
echo.

REM Cleanup
del %TOKEN_FILE% 2>nul
del %RESPONSE_FILE% 2>nul

endlocal
