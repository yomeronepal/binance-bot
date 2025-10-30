#!/bin/bash

# Walk-Forward Optimization Test Script
# This script tests the walk-forward optimization feature end-to-end

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
echo -e "${BLUE}Walk-Forward Optimization Test${NC}"
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

# Step 2: Create Walk-Forward Configuration
echo -e "${YELLOW}[2/5] Creating walk-forward optimization run...${NC}"

RESPONSE=$(curl -s -X POST "$API_URL/api/walkforward/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Walk-Forward - BTCUSDT",
    "symbols": ["BTCUSDT"],
    "timeframe": "5m",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-03-31T23:59:59Z",
    "training_window_days": 30,
    "testing_window_days": 10,
    "step_days": 10,
    "parameter_ranges": {
      "rsi_period": [14, 21],
      "rsi_oversold": [25, 30],
      "rsi_overbought": [70, 75]
    },
    "optimization_method": "grid",
    "initial_capital": 10000,
    "position_size": 100
  }')

WALKFORWARD_ID=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ -z "$WALKFORWARD_ID" ]; then
    echo -e "${RED}✗ Failed to create walk-forward run${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Walk-forward run created (ID: $WALKFORWARD_ID)${NC}"
echo ""

# Step 3: Monitor Execution
echo -e "${YELLOW}[3/5] Monitoring execution...${NC}"
echo "This may take 30-60 seconds depending on data availability..."
echo ""

MAX_WAIT=120  # 2 minutes max
WAIT_TIME=0
STATUS="PENDING"

while [ "$STATUS" != "COMPLETED" ] && [ "$STATUS" != "FAILED" ] && [ $WAIT_TIME -lt $MAX_WAIT ]; do
    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))

    RESPONSE=$(curl -s "$API_URL/api/walkforward/$WALKFORWARD_ID/" \
      -H "Authorization: Bearer $TOKEN")

    STATUS=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
    TOTAL_WINDOWS=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['total_windows'])" 2>/dev/null)
    COMPLETED_WINDOWS=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['completed_windows'])" 2>/dev/null)

    if [ "$TOTAL_WINDOWS" != "0" ]; then
        PROGRESS=$((COMPLETED_WINDOWS * 100 / TOTAL_WINDOWS))
        echo -e "Status: $STATUS | Progress: $COMPLETED_WINDOWS/$TOTAL_WINDOWS windows ($PROGRESS%) | Time: ${WAIT_TIME}s"
    else
        echo -e "Status: $STATUS | Generating windows... | Time: ${WAIT_TIME}s"
    fi
done

echo ""

if [ "$STATUS" = "COMPLETED" ]; then
    echo -e "${GREEN}✓ Walk-forward optimization completed!${NC}"
elif [ "$STATUS" = "FAILED" ]; then
    echo -e "${RED}✗ Walk-forward optimization failed${NC}"
    ERROR_MSG=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null)
    echo "Error: $ERROR_MSG"
    exit 1
else
    echo -e "${YELLOW}⚠ Timeout reached. Status: $STATUS${NC}"
    echo "You can check progress manually at: $API_URL/api/walkforward/$WALKFORWARD_ID/"
fi
echo ""

# Step 4: Get Results
echo -e "${YELLOW}[4/5] Fetching results...${NC}"

RESPONSE=$(curl -s "$API_URL/api/walkforward/$WALKFORWARD_ID/" \
  -H "Authorization: Bearer $TOKEN")

echo "$RESPONSE" | python -c "
import sys, json
data = json.load(sys.stdin)

print('═══════════════════════════════════════')
print('          WALKFORWARD RESULTS          ')
print('═══════════════════════════════════════')
print(f'ID:                {data[\"id\"]}')
print(f'Name:              {data[\"name\"]}')
print(f'Status:            {data[\"status\"]}')
print(f'Total Windows:     {data[\"total_windows\"]}')
print(f'Completed Windows: {data[\"completed_windows\"]}')
print('')
print('--- Aggregate Metrics ---')
print(f'Avg In-Sample ROI:     {data[\"avg_in_sample_roi_formatted\"]}')
print(f'Avg Out-Sample ROI:    {data[\"avg_out_sample_roi_formatted\"]}')
print(f'Performance Degradation: {data[\"performance_degradation_formatted\"]}')
print(f'Consistency Score:     {data[\"consistency_score_formatted\"]}')
print(f'Robust Strategy:       {\"✓ YES\" if data[\"is_robust\"] else \"✗ NO\"}')
print('═══════════════════════════════════════')
" 2>/dev/null

echo ""

# Step 5: Get Window Details
echo -e "${YELLOW}[5/5] Fetching window details...${NC}"

WINDOWS=$(curl -s "$API_URL/api/walkforward/$WALKFORWARD_ID/windows/" \
  -H "Authorization: Bearer $TOKEN")

echo "$WINDOWS" | python -c "
import sys, json
windows = json.load(sys.stdin)

print('═══════════════════════════════════════')
print('           WINDOW RESULTS              ')
print('═══════════════════════════════════════')
print('')

for w in windows:
    print(f'Window {w[\"window_number\"]}:')
    print(f'  Training:   {w[\"training_start\"][:10]} to {w[\"training_end\"][:10]}')
    print(f'  Testing:    {w[\"testing_start\"][:10]} to {w[\"testing_end\"][:10]}')
    print(f'  Status:     {w[\"status\"]}')
    print(f'  Best Params: {w[\"best_params\"]}')
    print(f'  In-Sample:  {w[\"in_sample_total_trades\"]} trades, {w[\"in_sample_win_rate_formatted\"]} WR, {w[\"in_sample_roi_formatted\"]} ROI')
    print(f'  Out-Sample: {w[\"out_sample_total_trades\"]} trades, {w[\"out_sample_win_rate_formatted\"]} WR, {w[\"out_sample_roi_formatted\"]} ROI')

    if w[\"error_message\"]:
        print(f'  Error: {w[\"error_message\"]}')

    print('')

print('═══════════════════════════════════════')
" 2>/dev/null

echo ""
echo -e "${GREEN}Test completed successfully!${NC}"
echo ""
echo -e "${BLUE}View in browser:${NC}"
echo -e "  Dashboard: $API_URL/api/walkforward/$WALKFORWARD_ID/"
echo -e "  Windows:   $API_URL/api/walkforward/$WALKFORWARD_ID/windows/"
echo -e "  Metrics:   $API_URL/api/walkforward/$WALKFORWARD_ID/metrics/"
echo ""
