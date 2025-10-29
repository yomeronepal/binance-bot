@echo off
REM Binance Bot - Complete Startup Script for Windows
REM This script starts all services in the correct order

echo ========================================
echo Starting Binance Trading Bot...
echo ========================================
echo.

REM Step 1: Check if Docker is running
echo Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)
echo OK: Docker is running
echo.

REM Step 2: Stop any existing containers
echo Stopping existing containers...
docker-compose down 2>nul
echo.

REM Step 3: Build images
echo Building Docker images this may take several minutes...
docker-compose build --no-cache
echo.

REM Step 4: Start database and Redis first
echo Starting database and Redis...
docker-compose up -d postgres redis
echo Waiting for services to be ready...
timeout /t 10 /nobreak >nul
echo.

REM Step 5: Run migrations
echo Running database migrations...
docker-compose run --rm backend python manage.py migrate
echo.

REM Step 6: Create superuser (optional)
echo Creating superuser (skip if exists)...
docker-compose run --rm backend python manage.py createsuperuser --noinput --username admin --email admin@example.com 2>nul
if %errorlevel% neq 0 (
    echo Superuser already exists or skipped
)
echo.

REM Step 7: Start all services
echo Starting all services...
docker-compose up -d
echo.

REM Step 8: Show status
echo ========================================
echo All services started successfully!
echo ========================================
echo.
echo Access your application:
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:8000
echo   Admin:     http://localhost:8000/admin
echo   Flower:    http://localhost:5555
echo.
echo View logs:
echo   docker-compose logs -f backend
echo   docker-compose logs -f celery-worker
echo   docker-compose logs -f frontend
echo.
echo Stop all services:
echo   docker-compose down
echo.

REM Show running containers
docker-compose ps

echo.
echo Press any key to exit...
pause >nul
