#!/bin/bash

# Backtesting Test Script
# This script tests the backtesting feature end-to-end

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:8000"
TOKEN=""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Backtesting Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Generate JWT Token
echo -e "${YELLOW}[1/5] Generating JWT token...${NC}"
TOKEN=$(docker-compose exec -T backend python manage.py shell -c "
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()
user = User.objects.first()
if not user:
    print('ERROR: No user found')
    exit(1)
refresh = RefreshToken.for_user(user)
print(str(refresh.access_token))
" 2>/dev/null | tail -1)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}✗ Failed to generate token${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Token generated${NC}"
echo ""

# Step 2: Create Backtest Run
echo -e "${YELLOW}[2/5] Creating backtest run...${NC}"

RESPONSE=$(curl -s -X POST "$API_URL/api/backtest/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Backtest - BTCUSDT",
    "symbols": ["BTCUSDT"],
    "timeframe": "5m",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-02-01T23:59:59Z",
    "strategy_params": {
      "rsi_oversold": 30,
      "rsi_overbought": 70,
      "adx_min": 20,
      "volume_multiplier": 1.2
    },
    "initial_capital": 10000,
    "position_size": 100
  }')

BACKTEST_ID=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ -z "$BACKTEST_ID" ]; then
    echo -e "${RED}✗ Failed to create backtest run${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Backtest run created (ID: $BACKTEST_ID)${NC}"
echo ""

# Step 3: Monitor Execution
echo -e "${YELLOW}[3/5] Monitoring execution...${NC}"
echo "This may take 30-90 seconds depending on data availability..."
echo ""

MAX_WAIT=180  # 3 minutes max
WAIT_TIME=0
STATUS="PENDING"

while [ "$STATUS" != "COMPLETED" ] && [ "$STATUS" != "FAILED" ] && [ $WAIT_TIME -lt $MAX_WAIT ]; do
    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))

    RESPONSE=$(curl -s "$API_URL/api/backtest/$BACKTEST_ID/" \
      -H "Authorization: Bearer $TOKEN")

    STATUS=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)

    echo -e "Status: $STATUS | Time: ${WAIT_TIME}s"
done

echo ""

if [ "$STATUS" = "COMPLETED" ]; then
    echo -e "${GREEN}✓ Backtest completed!${NC}"
elif [ "$STATUS" = "FAILED" ]; then
    echo -e "${RED}✗ Backtest failed${NC}"
    ERROR_MSG=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null)
    echo "Error: $ERROR_MSG"
    exit 1
else
    echo -e "${YELLOW}⚠ Timeout reached. Status: $STATUS${NC}"
    echo "You can check progress manually at: $API_URL/api/backtest/$BACKTEST_ID/"
fi
echo ""

# Step 4: Get Results
echo -e "${YELLOW}[4/5] Fetching results...${NC}"

RESPONSE=$(curl -s "$API_URL/api/backtest/$BACKTEST_ID/" \
  -H "Authorization: Bearer $TOKEN")

echo "$RESPONSE" | python -c "
import sys, json
data = json.load(sys.stdin)

print('═══════════════════════════════════════')
print('           BACKTEST RESULTS            ')
print('═══════════════════════════════════════')
print(f'ID:              {data[\"id\"]}')
print(f'Name:            {data[\"name\"]}')
print(f'Status:          {data[\"status\"]}')
print(f'Symbols:         {\", \".join(data[\"symbols\"])}')
print(f'Timeframe:       {data[\"timeframe\"]}')
print(f'Period:          {data[\"start_date\"][:10]} to {data[\"end_date\"][:10]}')
print('')
print('--- Performance Metrics ---')
print(f'Total Trades:    {data[\"total_trades\"]}')
print(f'Winning Trades:  {data[\"winning_trades\"]}')
print(f'Losing Trades:   {data[\"losing_trades\"]}')
print(f'Win Rate:        {data[\"win_rate_formatted\"]}')
print(f'Total P/L:       \${data[\"total_profit_loss\"]}')
print(f'ROI:             {data[\"roi_formatted\"]}')
print(f'Max Drawdown:    {data[\"max_drawdown_formatted\"]}')
print(f'Sharpe Ratio:    {data.get(\"sharpe_ratio\", \"N/A\")}')
print(f'Profit Factor:   {data.get(\"profit_factor\", \"N/A\")}')
print('═══════════════════════════════════════')
" 2>/dev/null

echo ""

# Step 5: Get Trades (first 10)
echo -e "${YELLOW}[5/5] Fetching trades...${NC}"

TRADES=$(curl -s "$API_URL/api/backtest/$BACKTEST_ID/trades/" \
  -H "Authorization: Bearer $TOKEN")

TRADE_COUNT=$(echo $TRADES | python -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null)

if [ "$TRADE_COUNT" = "0" ]; then
    echo "No trades executed (signals didn't trigger in test period)"
else
    echo "Showing first 10 trades (total: $TRADE_COUNT):"
    echo ""
    echo "$TRADES" | python -c "
import sys, json
trades = json.load(sys.stdin)[:10]

for t in trades:
    pnl = float(t['profit_loss'])
    pnl_sign = '+' if pnl >= 0 else ''
    status_symbol = '✓' if t['status'] == 'CLOSED_PROFIT' else '✗' if t['status'] == 'CLOSED_LOSS' else '○'

    print(f\"{status_symbol} {t['symbol']} {t['direction']:<5} | Entry: \${t['entry_price']:<8} Exit: \${t['exit_price']:<8} | P/L: {pnl_sign}\${pnl:.2f} ({t['profit_loss_percentage']:.2f}%) | {t['opened_at'][:10]}\")
" 2>/dev/null
fi

echo ""
echo "═══════════════════════════════════════"
echo ""
echo -e "${GREEN}Test completed successfully!${NC}"
echo ""
echo -e "${BLUE}View in browser:${NC}"
echo -e "  Dashboard: $API_URL/api/backtest/$BACKTEST_ID/"
echo -e "  Trades:    $API_URL/api/backtest/$BACKTEST_ID/trades/"
echo -e "  Metrics:   $API_URL/api/backtest/$BACKTEST_ID/metrics/"
echo -e "  Admin:     $API_URL/admin/signals/backtestrun/$BACKTEST_ID/change/"
echo ""
