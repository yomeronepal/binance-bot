#!/bin/bash
# Test script for Django management commands

echo "=========================================="
echo "Testing Django Management Commands"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check if commands exist
echo "1. Checking if commands are registered..."
echo ""

commands=(
    "analyze_trades"
    "analyze_performance"
    "clean_database"
    "create_paper_account"
    "monitor_backtests"
)

for cmd in "${commands[@]}"; do
    if docker-compose exec -T backend python manage.py help "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $cmd - Found"
    else
        echo -e "${RED}✗${NC} $cmd - Not found"
    fi
done

echo ""
echo "=========================================="
echo "2. Testing command help system..."
echo "=========================================="
echo ""

# Test help for one command
echo "Testing: python manage.py analyze_trades --help"
docker-compose exec -T backend python manage.py analyze_trades --help

echo ""
echo "=========================================="
echo "3. Verifying file locations..."
echo "=========================================="
echo ""

files=(
    "/app/signals/management/commands/analyze_trades.py"
    "/app/signals/management/commands/analyze_performance.py"
    "/app/signals/management/commands/clean_database.py"
    "/app/signals/management/commands/create_paper_account.py"
    "/app/signals/management/commands/monitor_backtests.py"
)

for file in "${files[@]}"; do
    if docker-compose exec -T backend test -f "$file" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file - Not found"
    fi
done

echo ""
echo "=========================================="
echo "4. Testing actual command execution..."
echo "=========================================="
echo ""

# Test create_paper_account with help
echo "Testing: python manage.py create_paper_account --help"
docker-compose exec -T backend python manage.py create_paper_account --help

echo ""
echo "=========================================="
echo "All tests complete!"
echo "=========================================="
