@echo off
REM Test script for Django management commands (Windows)

echo ==========================================
echo Testing Django Management Commands
echo ==========================================
echo.

REM Test 1: Check if commands exist
echo 1. Checking if commands are registered...
echo.

docker-compose exec -T backend python manage.py help analyze_trades >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] analyze_trades - Found
) else (
    echo [FAIL] analyze_trades - Not found
)

docker-compose exec -T backend python manage.py help analyze_performance >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] analyze_performance - Found
) else (
    echo [FAIL] analyze_performance - Not found
)

docker-compose exec -T backend python manage.py help clean_database >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] clean_database - Found
) else (
    echo [FAIL] clean_database - Not found
)

docker-compose exec -T backend python manage.py help create_paper_account >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] create_paper_account - Found
) else (
    echo [FAIL] create_paper_account - Not found
)

docker-compose exec -T backend python manage.py help monitor_backtests >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] monitor_backtests - Found
) else (
    echo [FAIL] monitor_backtests - Not found
)

echo.
echo ==========================================
echo 2. Testing command help system...
echo ==========================================
echo.

echo Testing: python manage.py analyze_trades --help
docker-compose exec -T backend python manage.py analyze_trades --help

echo.
echo ==========================================
echo All basic tests complete!
echo ==========================================
echo.
echo To test actual functionality, run:
echo   docker-compose exec backend python manage.py create_paper_account
echo   docker-compose exec backend python manage.py analyze_trades
echo.

pause
