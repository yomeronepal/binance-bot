#!/bin/bash

# Binance Bot - Complete Startup Script
# This script starts all services in the correct order

set -e  # Exit on error

echo "🚀 Starting Binance Trading Bot..."
echo "=================================="

# Colors for output
GREEN='\033[0.32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check if Docker is running
echo -e "${YELLOW}Checking Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi
echo -e "${GREEN}✅ Docker is running${NC}"

# Step 2: Stop any existing containers
echo -e "${YELLOW}Stopping existing containers...${NC}"
docker-compose down 2>/dev/null || true

# Step 3: Build images
echo -e "${YELLOW}Building Docker images (this may take several minutes)...${NC}"
docker-compose build --no-cache

# Step 4: Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d postgres redis

echo "Waiting for database and Redis to be ready..."
sleep 10

# Step 5: Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker-compose run --rm backend python manage.py migrate

# Step 6: Create superuser (if needed)
echo -e "${YELLOW}Creating superuser (skip if already exists)...${NC}"
docker-compose run --rm backend python manage.py createsuperuser --noinput --username admin --email admin@example.com 2>/dev/null || echo "Superuser already exists"

# Step 7: Start all services
echo -e "${YELLOW}Starting all services...${NC}"
docker-compose up -d

# Step 8: Show status
echo ""
echo -e "${GREEN}=================================="
echo "✅ All services started!"
echo "==================================${NC}"
echo ""
echo "📊 Access your application:"
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8000"
echo "   Admin:     http://localhost:8000/admin"
echo "   Flower:    http://localhost:5555"
echo ""
echo "📝 View logs:"
echo "   docker-compose logs -f backend"
echo "   docker-compose logs -f celery-worker"
echo "   docker-compose logs -f frontend"
echo ""
echo "🛑 Stop all services:"
echo "   docker-compose down"
echo ""

# Show running containers
docker-compose ps
