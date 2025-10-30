@echo off
REM Walk-Forward Optimization Test Script (Windows)
REM This script tests the walk-forward optimization feature end-to-end

setlocal enabledelayedexpansion

echo ========================================
echo Walk-Forward Optimization Test
echo ========================================
echo.

REM Configuration
set API_URL=http://localhost:8000
set TOKEN_FILE=%TEMP%\wf_token.txt
set RESPONSE_FILE=%TEMP%\wf_response.json

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

REM Step 2: Create Walk-Forward Run
echo [2/5] Creating walk-forward optimization run...

curl -s -X POST "%API_URL%/api/walkforward/" ^
  -H "Authorization: Bearer %TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Test Walk-Forward - BTCUSDT\",\"symbols\":[\"BTCUSDT\"],\"timeframe\":\"5m\",\"start_date\":\"2024-01-01T00:00:00Z\",\"end_date\":\"2024-03-31T23:59:59Z\",\"training_window_days\":30,\"testing_window_days\":10,\"step_days\":10,\"parameter_ranges\":{\"rsi_period\":[14,21],\"rsi_oversold\":[25,30],\"rsi_overbought\":[70,75]},\"optimization_method\":\"grid\",\"initial_capital\":10000,\"position_size\":100}" > %RESPONSE_FILE%

REM Extract ID from JSON response
for /f "tokens=2 delims=:," %%a in ('type %RESPONSE_FILE% ^| findstr /r "\"id\":[0-9]"') do set WALKFORWARD_ID=%%a
set WALKFORWARD_ID=%WALKFORWARD_ID: =%

if "%WALKFORWARD_ID%"=="" (
    echo [ERROR] Failed to create walk-forward run
    type %RESPONSE_FILE%
    exit /b 1
)

echo [OK] Walk-forward run created (ID: %WALKFORWARD_ID%)
echo.

REM Step 3: Monitor Execution
echo [3/5] Monitoring execution...
echo This may take 30-60 seconds...
echo.

set MAX_WAIT=120
set WAIT_TIME=0
set STATUS=PENDING

:MONITOR_LOOP
if %WAIT_TIME% GEQ %MAX_WAIT% goto TIMEOUT
if "%STATUS%"=="COMPLETED" goto COMPLETED
if "%STATUS%"=="FAILED" goto FAILED

timeout /t 5 /nobreak >nul
set /a WAIT_TIME+=5

curl -s "%API_URL%/api/walkforward/%WALKFORWARD_ID%/" ^
  -H "Authorization: Bearer %TOKEN%" > %RESPONSE_FILE%

REM Extract status from JSON
for /f "tokens=2 delims=:," %%a in ('type %RESPONSE_FILE% ^| findstr "\"status\""') do (
    set STATUS=%%a
    set STATUS=!STATUS:"=!
    set STATUS=!STATUS: =!
)

echo Status: %STATUS% ^| Time: %WAIT_TIME%s
goto MONITOR_LOOP

:TIMEOUT
echo [WARNING] Timeout reached
echo Check progress at: %API_URL%/api/walkforward/%WALKFORWARD_ID%/
goto RESULTS

:FAILED
echo [ERROR] Walk-forward optimization failed
type %RESPONSE_FILE% | findstr "error_message"
exit /b 1

:COMPLETED
echo [OK] Walk-forward optimization completed!
echo.

:RESULTS
REM Step 4: Get Results
echo [4/5] Fetching results...

curl -s "%API_URL%/api/walkforward/%WALKFORWARD_ID%/" ^
  -H "Authorization: Bearer %TOKEN%" > %RESPONSE_FILE%

echo =======================================
echo          WALKFORWARD RESULTS
echo =======================================
type %RESPONSE_FILE% | python -m json.tool 2>nul | findstr /i "\"id\" \"name\" \"status\" \"total_windows\" \"completed_windows\" \"avg_\" \"is_robust\" \"consistency\""
echo =======================================
echo.

REM Step 5: Get Window Details
echo [5/5] Fetching window details...

curl -s "%API_URL%/api/walkforward/%WALKFORWARD_ID%/windows/" ^
  -H "Authorization: Bearer %TOKEN%" | python -m json.tool 2>nul | more

echo.
echo =======================================
echo Test completed!
echo =======================================
echo.
echo View in browser:
echo   Dashboard: %API_URL%/api/walkforward/%WALKFORWARD_ID%/
echo   Windows:   %API_URL%/api/walkforward/%WALKFORWARD_ID%/windows/
echo   Metrics:   %API_URL%/api/walkforward/%WALKFORWARD_ID%/metrics/
echo.

REM Cleanup
del %TOKEN_FILE% 2>nul
del %RESPONSE_FILE% 2>nul

endlocal
