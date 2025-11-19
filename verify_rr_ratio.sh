#!/bin/bash
echo "======================================================================"
echo "🔍 VERIFYING 1:3 RISK/REWARD RATIO IMPLEMENTATION"
echo "======================================================================"
echo ""

echo "1️⃣  Checking Git Status..."
git log --oneline -1 | grep -i "risk/reward" && echo "✅ Latest commit includes R/R changes" || echo "❌ R/R changes not in latest commit"
echo ""

echo "2️⃣  Checking Code Implementation..."
grep -q "risk_reward_ratio.*3\.0" backend/scanner/strategies/signal_engine.py && echo "✅ SignalConfig has risk_reward_ratio = 3.0" || echo "❌ Missing risk_reward_ratio"
grep -q "reward = risk \* config.risk_reward_ratio" backend/scanner/strategies/signal_engine.py && echo "✅ _create_signal uses risk * RR formula" || echo "❌ Missing RR calculation"
grep -q "reward = risk \* 3\.0" backend/scanner/strategies/signal_generator.py && echo "✅ SignalGenerator uses risk * 3.0" || echo "❌ Missing RR in SignalGenerator"
echo ""

echo "3️⃣  Checking Docker Containers..."
docker ps --filter "name=docker-web-1" --format "{{.Names}}: {{.Status}}" | grep -q "Up" && echo "✅ Web container running" || echo "❌ Web container not running"
docker ps --filter "name=docker-worker-1" --format "{{.Names}}: {{.Status}}" | grep -q "Up" && echo "✅ Worker container running" || echo "❌ Worker container not running"
echo ""

echo "4️⃣  Running Test Suite..."
python3 test_rr_ratio.py | tail -3
echo ""

echo "5️⃣  Checking Recent Logs..."
echo "Looking for R/R ratio logs (last 20 lines):"
docker logs docker-worker-1 2>&1 | grep -i "r/r" | tail -5 || echo "⚠️  No R/R logs yet (wait for new signals to be generated)"
echo ""

echo "======================================================================"
echo "✅ VERIFICATION COMPLETE"
echo "======================================================================"
echo ""
echo "📋 Next Steps:"
echo "   1. Monitor logs: docker logs -f docker-worker-1 | grep '📐'"
echo "   2. Wait for new signals to be generated"
echo "   3. Verify R/R=1:3.00 in logs and UI"
echo ""
