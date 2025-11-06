@echo off
REM Trading Bot Quick Commands (Windows)
REM Usage: run.bat <command>

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="setup" goto setup
if "%1"=="download-long" goto download-long
if "%1"=="test-long" goto test-long
if "%1"=="optimize" goto optimize
if "%1"=="docker-restart" goto docker-restart
if "%1"=="shell" goto shell

echo Unknown command: %1
goto help

:help
echo ========================================
echo Trading Bot - Quick Commands
echo ========================================
echo.
echo Usage: run.bat ^<command^>
echo.
echo Available commands:
echo   help            - Show this help
echo   setup           - Verify Docker containers
echo   download-long   - Download 11-month data
echo   test-long       - Run extended backtest
echo   optimize        - Run parameter optimization
echo   docker-restart  - Restart containers
echo   shell           - Open backend shell
echo.
echo Examples:
echo   run.bat download-long
echo   run.bat test-long
echo   run.bat optimize
echo.
goto end

:setup
echo Checking Docker containers...
docker ps | findstr binance-bot
if errorlevel 1 (
    echo ERROR: Containers not running!
    echo Start with: docker-compose up -d
    exit /b 1
)
echo OK: Containers running
goto end

:download-long
echo Downloading 11-month historical data...
docker exec binance-bot-backend python scripts/data/download_long_period.py
docker exec binance-bot-backend bash -c "cp -r backtest_data_extended/* backtest_data/"
echo Done!
goto end

:test-long
echo Running extended period backtest...
docker exec binance-bot-backend python scripts/testing/test_extended_period.py
goto end

:optimize
echo Running parameter optimization...
docker exec binance-bot-backend python scripts/optimization/optimize_parameters_final.py
goto end

:docker-restart
echo Restarting Docker containers...
docker restart binance-bot-backend binance-bot-celery-worker binance-bot-db binance-bot-redis
timeout /t 3 /nobreak > nul
echo Done!
goto end

:shell
echo Opening shell in backend container...
docker exec -it binance-bot-backend bash
goto end

:end
