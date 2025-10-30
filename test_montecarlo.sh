#!/bin/bash

# Monte Carlo Simulation Test Script
# This script tests the Monte Carlo simulation feature end-to-end

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
echo -e "${BLUE}Monte Carlo Simulation Test${NC}"
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

# Step 2: Create Monte Carlo Simulation
echo -e "${YELLOW}[2/5] Creating Monte Carlo simulation...${NC}"

RESPONSE=$(curl -s -X POST "$API_URL/api/montecarlo/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @test_montecarlo.json)

SIMULATION_ID=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ -z "$SIMULATION_ID" ]; then
    echo -e "${RED}✗ Failed to create Monte Carlo simulation${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Monte Carlo simulation created (ID: $SIMULATION_ID)${NC}"
echo ""

# Step 3: Monitor Execution
echo -e "${YELLOW}[3/5] Monitoring execution...${NC}"
echo "This may take 1-5 minutes depending on number of simulations..."
echo ""

MAX_WAIT=600  # 10 minutes max
WAIT_TIME=0
STATUS="PENDING"

while [ "$STATUS" != "COMPLETED" ] && [ "$STATUS" != "FAILED" ] && [ $WAIT_TIME -lt $MAX_WAIT ]; do
    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))

    RESPONSE=$(curl -s "$API_URL/api/montecarlo/$SIMULATION_ID/" \
      -H "Authorization: Bearer $TOKEN")

    STATUS=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
    PROGRESS=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['progress_percentage'])" 2>/dev/null)
    COMPLETED=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['completed_simulations'])" 2>/dev/null)
    TOTAL=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['num_simulations'])" 2>/dev/null)

    echo -e "Status: $STATUS | Progress: $COMPLETED/$TOTAL ($PROGRESS%) | Time: ${WAIT_TIME}s"
done

echo ""

if [ "$STATUS" = "COMPLETED" ]; then
    echo -e "${GREEN}✓ Monte Carlo simulation completed!${NC}"
elif [ "$STATUS" = "FAILED" ]; then
    echo -e "${RED}✗ Monte Carlo simulation failed${NC}"
    ERROR_MSG=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null)
    echo "Error: $ERROR_MSG"
    exit 1
else
    echo -e "${YELLOW}⚠ Timeout reached. Status: $STATUS${NC}"
    echo "You can check progress manually at: $API_URL/api/montecarlo/$SIMULATION_ID/"
fi
echo ""

# Step 4: Get Results
echo -e "${YELLOW}[4/5] Fetching results...${NC}"

RESPONSE=$(curl -s "$API_URL/api/montecarlo/$SIMULATION_ID/" \
  -H "Authorization: Bearer $TOKEN")

echo "$RESPONSE" | python -c "
import sys, json
data = json.load(sys.stdin)

print('═══════════════════════════════════════')
print('      MONTE CARLO RESULTS             ')
print('═══════════════════════════════════════')
print(f'ID:              {data[\"id\"]}')
print(f'Name:            {data[\"name\"]}')
print(f'Status:          {data[\"status\"]}')
print(f'Symbols:         {\", \".join(data[\"symbols\"])}')
print(f'Timeframe:       {data[\"timeframe\"]}')
print(f'Period:          {data[\"start_date\"][:10]} to {data[\"end_date\"][:10]}')
print(f'Simulations:     {data[\"completed_simulations\"]}/{data[\"num_simulations\"]}')
print('')
print('--- Statistical Results ---')
print(f'Expected Return: {data[\"mean_return_formatted\"]}')
print(f'Median Return:   {data[\"median_return_formatted\"]}')
print(f'Std Deviation:   {data[\"std_deviation\"]}%')
print(f'Best Case:       +{data[\"best_case_return\"]}%')
print(f'Worst Case:      {data[\"worst_case_return\"]}%')
print('')
print('--- Confidence Intervals ---')
print(f'95% Confidence:  {data[\"confidence_95_formatted\"]}')
print(f'99% Confidence:  {data[\"confidence_99_formatted\"]}')
print('')
print('--- Probability Metrics ---')
print(f'Prob of Profit:  {data[\"probability_of_profit_formatted\"]}')
print(f'Prob of Loss:    {data[\"probability_of_loss_formatted\"]}')
print('')
print('--- Risk Metrics ---')
print(f'VaR at 95%:      {data[\"var_95_formatted\"]}')
print(f'VaR at 99%:      {data[\"var_99_formatted\"]}')
print(f'Mean Drawdown:   {data[\"mean_max_drawdown\"]}%')
print(f'Worst Drawdown:  {data[\"worst_case_drawdown\"]}%')
print('')
print('--- Performance Metrics ---')
print(f'Mean Sharpe:     {data[\"mean_sharpe_ratio\"]}')
print(f'Mean Win Rate:   {data[\"mean_win_rate\"]}%')
print('')
print('--- Robustness Assessment ---')
print(f'Robust:          {\"YES\" if data[\"is_statistically_robust\"] else \"NO\"}')
print(f'Score:           {data[\"robustness_score\"]}/100')
print(f'Label:           {data[\"robustness_label\"]}')
print('═══════════════════════════════════════')
" 2>/dev/null

echo ""

# Step 5: Get Best/Worst Runs
echo -e "${YELLOW}[5/5] Fetching best/worst runs...${NC}"

RUNS=$(curl -s "$API_URL/api/montecarlo/$SIMULATION_ID/best_worst_runs/?n=5" \
  -H "Authorization: Bearer $TOKEN")

echo "Best 5 Runs:"
echo "$RUNS" | python -c "
import sys, json
data = json.load(sys.stdin)

for run in data['best_runs']:
    roi = float(run['roi'])
    print(f\"  Run #{run['run_number']}: ROI {roi:+.2f}%, Win Rate {run['win_rate']:.1f}%, Sharpe {run['sharpe_ratio']:.2f}\")
" 2>/dev/null

echo ""
echo "Worst 5 Runs:"
echo "$RUNS" | python -c "
import sys, json
data = json.load(sys.stdin)

for run in data['worst_runs']:
    roi = float(run['roi'])
    print(f\"  Run #{run['run_number']}: ROI {roi:+.2f}%, Win Rate {run['win_rate']:.1f}%, Sharpe {run['sharpe_ratio']:.2f}\")
" 2>/dev/null

echo ""
echo "═══════════════════════════════════════"
echo ""
echo -e "${GREEN}Test completed successfully!${NC}"
echo ""
echo -e "${BLUE}View in browser:${NC}"
echo -e "  Summary:       $API_URL/api/montecarlo/$SIMULATION_ID/summary/"
echo -e "  All Runs:      $API_URL/api/montecarlo/$SIMULATION_ID/runs/"
echo -e "  Distributions: $API_URL/api/montecarlo/$SIMULATION_ID/distributions/"
echo -e "  Admin:         $API_URL/admin/signals/montecarlosimulation/$SIMULATION_ID/change/"
echo ""
