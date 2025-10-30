#!/bin/bash

# ML Tuning Test Script
# Tests the ML-based parameter optimization feature end-to-end

set -e

API_URL="http://localhost:8000"
CONFIG_FILE="test_mltuning_quick.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "ML Tuning Test"
echo "========================================"
echo ""

# Step 1: Generate JWT token
echo -e "${BLUE}[1/5] Generating JWT token...${NC}"
TOKEN=$(docker-compose exec -T backend python manage.py shell -c "
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
User = get_user_model()
user = User.objects.first()
if user:
    refresh = RefreshToken.for_user(user)
    print(str(refresh.access_token))
else:
    print('ERROR: No user found')
    exit(1)
" 2>/dev/null | tail -n 1)

if [ "$TOKEN" == "ERROR: No user found" ] || [ -z "$TOKEN" ]; then
    echo -e "${RED}✗ Failed to generate token. Please create a user first:${NC}"
    echo "  docker-compose exec backend python manage.py createsuperuser"
    exit 1
fi

echo -e "${GREEN}✓ Token generated${NC}"
echo ""

# Step 2: Create ML tuning job
echo -e "${BLUE}[2/5] Creating ML tuning job...${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/api/mltuning/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @"$CONFIG_FILE")

JOB_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")
TASK_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null || echo "")

if [ -z "$JOB_ID" ] || [ -z "$TASK_ID" ]; then
    echo -e "${RED}✗ Failed to create ML tuning job${NC}"
    echo "$RESPONSE" | python -m json.tool 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ ML tuning job created (ID: $JOB_ID)${NC}"
echo "  Task ID: $TASK_ID"
echo ""

# Step 3: Monitor execution
echo -e "${BLUE}[3/5] Monitoring execution...${NC}"
echo "This may take 5-15 minutes depending on number of samples..."
echo ""

TIMEOUT=900  # 15 minutes
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $TIMEOUT ]; do
    STATUS_RESPONSE=$(curl -s "$API_URL/api/mltuning/$JOB_ID/" \
      -H "Authorization: Bearer $TOKEN")

    STATUS=$(echo "$STATUS_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('status', 'UNKNOWN'))" 2>/dev/null || echo "ERROR")
    PROGRESS=$(echo "$STATUS_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('samples_evaluated', 0))" 2>/dev/null || echo "0")
    TOTAL=$(echo "$STATUS_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('num_training_samples', 0))" 2>/dev/null || echo "0")

    if [ "$STATUS" == "COMPLETED" ]; then
        echo -e "\n${GREEN}✓ ML tuning job completed!${NC}"
        break
    elif [ "$STATUS" == "FAILED" ]; then
        ERROR_MSG=$(echo "$STATUS_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
        echo -e "\n${RED}✗ ML tuning job failed: $ERROR_MSG${NC}"
        exit 1
    elif [ "$STATUS" == "RUNNING" ]; then
        PERCENT=$((PROGRESS * 100 / TOTAL))
        printf "\r${YELLOW}Status: RUNNING | Progress: $PROGRESS/$TOTAL ($PERCENT%%) | Time: ${ELAPSED}s${NC}"
    elif [ "$STATUS" == "PENDING" ]; then
        printf "\r${YELLOW}Status: PENDING | Waiting for worker... | Time: ${ELAPSED}s${NC}"
    else
        printf "\r${YELLOW}Status: $STATUS | Progress: $PROGRESS/$TOTAL | Time: ${ELAPSED}s${NC}"
    fi

    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo -e "\n${RED}✗ Timeout reached (${TIMEOUT}s). Job may still be running.${NC}"
    echo "Check status manually:"
    echo "  curl $API_URL/api/mltuning/$JOB_ID/ -H 'Authorization: Bearer $TOKEN' | python -m json.tool"
    exit 1
fi

echo ""

# Step 4: Fetch results
echo -e "${BLUE}[4/5] Fetching results...${NC}"
SUMMARY=$(curl -s "$API_URL/api/mltuning/$JOB_ID/summary/" \
  -H "Authorization: Bearer $TOKEN")

echo "═══════════════════════════════════════"
echo "      ML TUNING RESULTS"
echo "═══════════════════════════════════════"

# Parse and display summary
echo "$SUMMARY" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"ID:              {data.get('id', 'N/A')}\")
    print(f\"Name:            {data.get('name', 'N/A')}\")
    print(f\"Status:          {data.get('status', 'N/A')}\")
    print(f\"ML Algorithm:    {data.get('ml_algorithm', 'N/A')}\")
    print(f\"Metric:          {data.get('optimization_metric', 'N/A')}\")
    print(f\"Symbols:         {', '.join(data.get('symbols', []))}\")
    print(f\"Timeframe:       {data.get('timeframe', 'N/A')}\")
    print(f\"Training Period: {data.get('training_start_date', 'N/A')[:10]} to {data.get('training_end_date', 'N/A')[:10]}\")
    print()

    training = data.get('training', {})
    print('--- Training Results ---')
    print(f\"Samples:         {training.get('samples', 'N/A')}/{data.get('num_training_samples', 'N/A')}\")
    print(f\"R² Score:        {training.get('r2_score', 'N/A'):.4f}\")
    print(f\"Validation R²:   {training.get('validation_r2', 'N/A'):.4f}\")
    print(f\"Overfitting:     {training.get('overfitting', 'N/A'):.4f}\")
    print()

    print('--- Best Parameters Found ---')
    best_params = data.get('best_parameters', {})
    for key, value in best_params.items():
        print(f\"  {key}: {value}\")
    print()

    print(f\"Predicted Performance: {data.get('predicted_performance', 'N/A'):.4f}\")
    print()

    out_of_sample = data.get('out_of_sample', {})
    print('--- Out-of-Sample Validation ---')
    print(f\"ROI:             {out_of_sample.get('roi', 'N/A'):.2f}%\")
    print(f\"Sharpe Ratio:    {out_of_sample.get('sharpe', 'N/A'):.4f}\")
    print(f\"Win Rate:        {out_of_sample.get('win_rate', 'N/A'):.2f}%\")
    print()

    quality = data.get('quality', {})
    print('--- Model Quality ---')
    print(f\"Quality Score:   {quality.get('score', 'N/A'):.1f}/100\")
    print(f\"Production Ready: {'YES' if quality.get('production_ready') else 'NO'}\")
    print()

    print(f\"Execution Time:  {data.get('execution_time', 'N/A'):.1f}s\")
except Exception as e:
    print(f'Error parsing summary: {e}')
    print('Raw response:')
    print(sys.stdin.read())
"

echo "═══════════════════════════════════════"
echo ""

# Step 5: Fetch feature importance
echo -e "${BLUE}[5/5] Fetching feature importance...${NC}"
IMPORTANCE=$(curl -s "$API_URL/api/mltuning/$JOB_ID/feature_importance/" \
  -H "Authorization: Bearer $TOKEN")

echo "Top 10 Most Important Features:"
echo "$IMPORTANCE" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    top_10 = data.get('top_10', {})
    for i, (feature, importance) in enumerate(top_10.items(), 1):
        bar_length = int(importance * 50)
        bar = '█' * bar_length
        print(f\"  {i:2d}. {feature:25s} {bar} {importance:.4f}\")
except Exception as e:
    print(f'Error parsing feature importance: {e}')
" 2>/dev/null || echo "Feature importance not available"

echo ""
echo "═══════════════════════════════════════"
echo ""
echo -e "${GREEN}Test completed successfully!${NC}"
echo ""
echo "View in browser:"
echo "  Summary:       $API_URL/api/mltuning/$JOB_ID/summary/"
echo "  Feature Imp:   $API_URL/api/mltuning/$JOB_ID/feature_importance/"
echo "  Sensitivity:   $API_URL/api/mltuning/$JOB_ID/sensitivity/"
echo "  Samples:       $API_URL/api/mltuning/$JOB_ID/samples/"
echo "  Admin:         $API_URL/admin/signals/mltuningjob/$JOB_ID/change/"
echo ""
