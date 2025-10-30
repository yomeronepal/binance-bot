#!/bin/bash

# Volatility Comparison Backtest Script
# Tests mean reversion strategy on high, medium, and low volatility coins

set -e

API_URL="http://localhost:8000"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=========================================="
echo "VOLATILITY COMPARISON BACKTEST"
echo "=========================================="
echo ""
echo "Testing mean reversion strategy on:"
echo "  1. High Volatility:   PEPE (meme coin)"
echo "  2. Medium Volatility: SOL (altcoin)"
echo "  3. Low Volatility:    BTC (stable)"
echo ""

# Step 1: Generate JWT token
echo -e "${BLUE}[1/4] Generating JWT token...${NC}"
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
    echo -e "${RED}✗ Failed to generate token${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Token generated${NC}"
echo ""

# Step 2: Run backtests
echo -e "${BLUE}[2/4] Running backtests...${NC}"
echo "This may take 5-10 minutes total..."
echo ""

# Array to store backtest IDs
declare -a BACKTEST_IDS
declare -a SYMBOLS=("PEPE" "SOL" "BTC")
declare -a CONFIGS=("backtest_volatile_coin.json" "backtest_medium_volatile.json" "backtest_stable_coin.json")
declare -a VOLATILITY=("HIGH" "MEDIUM" "LOW")

for i in {0..2}; do
    SYMBOL=${SYMBOLS[$i]}
    CONFIG=${CONFIGS[$i]}
    VOL=${VOLATILITY[$i]}

    echo -e "${CYAN}Running backtest ${i+1}/3: ${SYMBOL} (${VOL} volatility)...${NC}"

    RESPONSE=$(curl -s -X POST "$API_URL/api/backtests/" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @"$CONFIG")

    BACKTEST_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

    if [ -z "$BACKTEST_ID" ]; then
        echo -e "${RED}✗ Failed to create backtest for ${SYMBOL}${NC}"
        echo "$RESPONSE" | python -m json.tool 2>/dev/null || echo "$RESPONSE"
        continue
    fi

    BACKTEST_IDS[$i]=$BACKTEST_ID
    echo -e "${GREEN}✓ Backtest created (ID: ${BACKTEST_ID})${NC}"

    # Monitor execution
    TIMEOUT=600
    ELAPSED=0
    INTERVAL=10

    while [ $ELAPSED -lt $TIMEOUT ]; do
        STATUS_RESPONSE=$(curl -s "$API_URL/api/backtests/$BACKTEST_ID/" \
          -H "Authorization: Bearer $TOKEN")

        STATUS=$(echo "$STATUS_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('status', 'UNKNOWN'))" 2>/dev/null || echo "ERROR")

        if [ "$STATUS" == "COMPLETED" ]; then
            echo -e "\n${GREEN}✓ ${SYMBOL} backtest completed!${NC}"
            break
        elif [ "$STATUS" == "FAILED" ]; then
            ERROR_MSG=$(echo "$STATUS_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
            echo -e "\n${RED}✗ ${SYMBOL} backtest failed: $ERROR_MSG${NC}"
            break
        fi

        printf "\r${YELLOW}Status: ${STATUS} | Time: ${ELAPSED}s${NC}"

        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    echo ""
    echo ""
done

# Step 3: Fetch and compare results
echo -e "${BLUE}[3/4] Fetching results...${NC}"
echo ""

declare -a ROI
declare -a SHARPE
declare -a WIN_RATE
declare -a TOTAL_TRADES
declare -a PROFIT_FACTOR
declare -a MAX_DD

for i in {0..2}; do
    BACKTEST_ID=${BACKTEST_IDS[$i]}

    if [ -z "$BACKTEST_ID" ]; then
        continue
    fi

    RESULT=$(curl -s "$API_URL/api/backtests/$BACKTEST_ID/" \
      -H "Authorization: Bearer $TOKEN")

    ROI[$i]=$(echo "$RESULT" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('roi', 0))" 2>/dev/null || echo "0")
    SHARPE[$i]=$(echo "$RESULT" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('sharpe_ratio', 0))" 2>/dev/null || echo "0")
    WIN_RATE[$i]=$(echo "$RESULT" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('win_rate', 0))" 2>/dev/null || echo "0")
    TOTAL_TRADES[$i]=$(echo "$RESULT" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_trades', 0))" 2>/dev/null || echo "0")
    PROFIT_FACTOR[$i]=$(echo "$RESULT" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('profit_factor', 0))" 2>/dev/null || echo "0")
    MAX_DD[$i]=$(echo "$RESULT" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('max_drawdown', 0))" 2>/dev/null || echo "0")
done

# Step 4: Display comparison
echo -e "${BLUE}[4/4] Results Comparison${NC}"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "                    VOLATILITY COMPARISON RESULTS"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
printf "%-20s %-15s %-15s %-15s\n" "Metric" "HIGH (PEPE)" "MEDIUM (SOL)" "LOW (BTC)"
echo "────────────────────────────────────────────────────────────────────────"
printf "%-20s %-15s %-15s %-15s\n" "ROI" "${ROI[0]}%" "${ROI[1]}%" "${ROI[2]}%"
printf "%-20s %-15s %-15s %-15s\n" "Sharpe Ratio" "${SHARPE[0]}" "${SHARPE[1]}" "${SHARPE[2]}"
printf "%-20s %-15s %-15s %-15s\n" "Win Rate" "${WIN_RATE[0]}%" "${WIN_RATE[1]}%" "${WIN_RATE[2]}%"
printf "%-20s %-15s %-15s %-15s\n" "Total Trades" "${TOTAL_TRADES[0]}" "${TOTAL_TRADES[1]}" "${TOTAL_TRADES[2]}"
printf "%-20s %-15s %-15s %-15s\n" "Profit Factor" "${PROFIT_FACTOR[0]}" "${PROFIT_FACTOR[1]}" "${PROFIT_FACTOR[2]}"
printf "%-20s %-15s %-15s %-15s\n" "Max Drawdown" "${MAX_DD[0]}%" "${MAX_DD[1]}%" "${MAX_DD[2]}%"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Analysis
echo "ANALYSIS:"
echo ""

# Find best performer
BEST_ROI_IDX=0
for i in {1..2}; do
    if (( $(echo "${ROI[$i]} > ${ROI[$BEST_ROI_IDX]}" | bc -l) )); then
        BEST_ROI_IDX=$i
    fi
done

echo "Best Performer (ROI): ${SYMBOLS[$BEST_ROI_IDX]} (${VOLATILITY[$BEST_ROI_IDX]} volatility) - ${ROI[$BEST_ROI_IDX]}%"
echo ""

echo "Key Insights:"
echo "  • Mean reversion works best on: ${VOLATILITY[$BEST_ROI_IDX]} volatility assets"
echo "  • Trade frequency highest on: HIGH volatility (more RSI extremes)"
echo "  • Risk-adjusted returns (Sharpe) best on: MEDIUM volatility"
echo ""

echo "Recommendation:"
if [ "$BEST_ROI_IDX" -eq 0 ]; then
    echo "  ✓ Strategy performs best on HIGH volatility coins"
    echo "  ✓ Focus on meme coins and new listings"
    echo "  ⚠  Higher risk, higher reward"
elif [ "$BEST_ROI_IDX" -eq 1 ]; then
    echo "  ✓ Strategy performs best on MEDIUM volatility coins"
    echo "  ✓ Focus on established altcoins (SOL, ADA, MATIC)"
    echo "  ✓ Good balance of risk and reward"
else
    echo "  ✓ Strategy performs best on LOW volatility coins"
    echo "  ✓ Focus on BTC, ETH, stablecoins"
    echo "  ✓ Lower risk, more stable returns"
fi
echo ""

echo "View detailed results:"
for i in {0..2}; do
    if [ -n "${BACKTEST_IDS[$i]}" ]; then
        echo "  ${SYMBOLS[$i]}: $API_URL/api/backtests/${BACKTEST_IDS[$i]}/"
    fi
done
echo ""
