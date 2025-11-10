#!/bin/bash

# Deployment script for Binance Trading Bot
# This script is executed on the server by GitHub Actions

set -e  # Exit on error

echo "=================================="
echo "Starting deployment..."
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/opt/binance-bot"
BACKUP_DIR="/opt/binance-bot-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Change to project directory
cd $PROJECT_DIR || exit 1

# Step 1: Backup current database (optional but recommended)
print_status "Creating database backup..."
mkdir -p $BACKUP_DIR
docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U postgres trading_bot > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql" 2>/dev/null || print_warning "Database backup failed (container might not be running)"

# Step 2: Stop existing containers
print_status "Stopping containers..."
docker-compose -f docker-compose.prod.yml down || print_warning "Containers were not running"

# Step 3: Pull latest images from Docker Hub
print_status "Pulling latest images from Docker Hub..."
docker-compose -f docker-compose.prod.yml pull

# Step 4: Start containers in detached mode
print_status "Starting containers..."
docker-compose -f docker-compose.prod.yml up -d

# Step 6: Wait for database to be ready
print_status "Waiting for database to be ready..."
sleep 5

# Step 7: Run database migrations
print_status "Running database migrations..."
docker-compose -f docker-compose.prod.yml exec -T web python manage.py migrate --noinput

# Step 8: Collect static files
print_status "Collecting static files..."
docker-compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput

# Step 9: Create superuser if needed (optional)
# docker-compose -f docker-compose.prod.yml exec -T web python manage.py createsuperuser --noinput --email admin@example.com || true

# Step 10: Restart Celery workers to pick up new code
print_status "Restarting Celery workers..."
docker-compose -f docker-compose.prod.yml restart celery

# Step 11: Clean up old Docker images and containers
print_status "Cleaning up old Docker images..."
docker system prune -f

# Step 12: Check service health
print_status "Checking service health..."
sleep 5

# Check if containers are running
if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    print_status "Containers are running:"
    docker-compose -f docker-compose.prod.yml ps
else
    print_error "Some containers are not running!"
    docker-compose -f docker-compose.prod.yml ps
    exit 1
fi

# Step 13: Keep only last 7 backups
print_status "Cleaning old backups..."
find $BACKUP_DIR -name "db_backup_*.sql" -mtime +7 -delete

echo ""
echo "=================================="
print_status "Deployment completed successfully!"
echo "=================================="
echo ""
print_status "Service status:"
docker-compose -f docker-compose.prod.yml ps
echo ""
print_status "To view logs, run: docker-compose -f docker-compose.prod.yml logs -f"
echo ""
