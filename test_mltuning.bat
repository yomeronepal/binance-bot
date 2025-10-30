@echo off
REM ML Tuning Test Script for Windows
REM Tests the ML-based parameter optimization feature end-to-end

setlocal enabledelayedexpansion

set API_URL=http://localhost:8000
set CONFIG_FILE=test_mltuning_quick.json

echo ========================================
echo ML Tuning Test
echo ========================================
echo.

REM Step 1: Generate JWT token
echo [1/5] Generating JWT token...
for /f "delims=" %%i in ('docker-compose exec -T backend python manage.py shell -c "from django.contrib.auth import get_user_model; from rest_framework_simplejwt.tokens import RefreshToken; User = get_user_model(); user = User.objects.first(); refresh = RefreshToken.for_user(user) if user else None; print(str(refresh.access_token)) if refresh else print('ERROR')" 2^>nul ^| findstr /v "^$"') do set TOKEN=%%i

if "!TOKEN!"=="ERROR" (
    echo x Failed to generate token. Please create a user first:
    echo   docker-compose exec backend python manage.py createsuperuser
    exit /b 1
)

echo √ Token generated
echo.

REM Step 2: Create ML tuning job
echo [2/5] Creating ML tuning job...
curl -s -X POST "%API_URL%/api/mltuning/" -H "Authorization: Bearer !TOKEN!" -H "Content-Type: application/json" -d @"%CONFIG_FILE%" > response.json

REM Parse job ID
for /f "tokens=*" %%i in ('python -c "import json; data=json.load(open('response.json')); print(data.get('id', ''))" 2^>nul') do set JOB_ID=%%i
for /f "tokens=*" %%i in ('python -c "import json; data=json.load(open('response.json')); print(data.get('task_id', ''))" 2^>nul') do set TASK_ID=%%i

if "!JOB_ID!"=="" (
    echo x Failed to create ML tuning job
    type response.json
    del response.json
    exit /b 1
)

echo √ ML tuning job created (ID: !JOB_ID!)
echo   Task ID: !TASK_ID!
echo.

REM Step 3: Monitor execution
echo [3/5] Monitoring execution...
echo This may take 5-15 minutes depending on number of samples...
echo.

set TIMEOUT=900
set ELAPSED=0
set INTERVAL=10

:monitor_loop
if !ELAPSED! GEQ !TIMEOUT! goto timeout_reached

curl -s "%API_URL%/api/mltuning/!JOB_ID!/" -H "Authorization: Bearer !TOKEN!" > status.json

for /f "tokens=*" %%i in ('python -c "import json; data=json.load(open('status.json')); print(data.get('status', 'UNKNOWN'))" 2^>nul') do set STATUS=%%i
for /f "tokens=*" %%i in ('python -c "import json; data=json.load(open('status.json')); print(data.get('samples_evaluated', 0))" 2^>nul') do set PROGRESS=%%i
for /f "tokens=*" %%i in ('python -c "import json; data=json.load(open('status.json')); print(data.get('num_training_samples', 0))" 2^>nul') do set TOTAL=%%i

if "!STATUS!"=="COMPLETED" (
    echo.
    echo √ ML tuning job completed!
    goto fetch_results
)

if "!STATUS!"=="FAILED" (
    echo.
    echo x ML tuning job failed
    type status.json | python -m json.tool 2>nul
    del status.json response.json
    exit /b 1
)

set /a PERCENT=!PROGRESS! * 100 / !TOTAL! 2>nul
echo Status: !STATUS! ^| Progress: !PROGRESS!/!TOTAL! (!PERCENT!%%) ^| Time: !ELAPSED!s

timeout /t !INTERVAL! /nobreak >nul
set /a ELAPSED=!ELAPSED! + !INTERVAL!
goto monitor_loop

:timeout_reached
echo.
echo x Timeout reached (!TIMEOUT!s). Job may still be running.
echo Check status manually:
echo   curl %API_URL%/api/mltuning/!JOB_ID!/ -H "Authorization: Bearer !TOKEN!" ^| python -m json.tool
del status.json response.json
exit /b 1

:fetch_results
echo.

REM Step 4: Fetch results
echo [4/5] Fetching results...
curl -s "%API_URL%/api/mltuning/!JOB_ID!/summary/" -H "Authorization: Bearer !TOKEN!" > summary.json

echo ===================================
echo       ML TUNING RESULTS
echo ===================================

python -c "import json; data=json.load(open('summary.json')); print('ID:', data.get('id')); print('Name:', data.get('name')); print('Status:', data.get('status')); print('ML Algorithm:', data.get('ml_algorithm')); print('\nTraining R² Score:', data.get('training', {}).get('r2_score')); print('Validation R²:', data.get('training', {}).get('validation_r2')); print('\nBest Parameters:', data.get('best_parameters')); print('\nOut-of-Sample ROI:', data.get('out_of_sample', {}).get('roi'), '%%'); print('Production Ready:', 'YES' if data.get('quality', {}).get('production_ready') else 'NO')" 2>nul

echo ===================================
echo.

REM Step 5: Feature importance
echo [5/5] Fetching feature importance...
curl -s "%API_URL%/api/mltuning/!JOB_ID!/feature_importance/" -H "Authorization: Bearer !TOKEN!" > importance.json

echo Top 10 Most Important Features:
python -c "import json; data=json.load(open('importance.json')); top=data.get('top_10', {}); [print(f'  {i}. {k}: {v:.4f}') for i, (k, v) in enumerate(top.items(), 1)]" 2>nul

echo.
echo √ Test completed successfully!
echo.
echo View in browser:
echo   Summary:       %API_URL%/api/mltuning/!JOB_ID!/summary/
echo   Feature Imp:   %API_URL%/api/mltuning/!JOB_ID!/feature_importance/
echo   Admin:         %API_URL%/admin/signals/mltuningjob/!JOB_ID!/change/
echo.

REM Cleanup
del status.json response.json summary.json importance.json 2>nul

endlocal
