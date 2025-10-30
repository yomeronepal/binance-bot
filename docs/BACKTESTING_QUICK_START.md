# Backtesting System - Quick Start Guide

## System Status

✅ **FULLY FUNCTIONAL** - All tests passed!

The backtesting system has been verified and is working correctly. All components are operational:
- ✅ Database models created and migrated
- ✅ Historical data fetcher working
- ✅ Backtesting engine functional
- ✅ Parameter optimizer ready
- ✅ Self-learning module operational
- ✅ API endpoints accessible
- ✅ Celery tasks registered

## How to Use Backtesting

### Method 1: Django Admin Panel (Easiest)

1. **Access Admin Panel**
   ```
   URL: http://localhost:8000/admin/
   Login: admin / admin123
   ```

2. **Navigate to Backtests**
   ```
   Go to: Signals → Backtest runs
   ```

3. **Create New Backtest**
   - Click "Add Backtest Run"
   - Fill in the form:
     - Name: "My First Backtest"
     - User: Select your user
     - Status: PENDING
     - Symbols: `["BTCUSDT", "ETHUSDT"]`
     - Timeframe: 5m
     - Start date: 2024-01-01 00:00:00
     - End date: 2024-01-31 23:59:59
     - Strategy params: `{}`
     - Initial capital: 10000
     - Position size: 100
   - Save

4. **Trigger Backtest Manually**
   ```bash
   # Via Django shell
   docker-compose exec backend python manage.py shell

   from scanner.tasks.backtest_tasks import run_backtest_async
   task = run_backtest_async.delay(1)  # Replace 1 with your backtest ID
   print(f"Task queued: {task.id}")
   ```

5. **Monitor Progress**
   ```bash
   # Watch Celery logs
   docker-compose logs -f celery-worker

   # Check backtest status in admin panel (refresh page)
   # Status will change: PENDING → RUNNING → COMPLETED
   ```

6. **View Results**
   - Go back to the backtest in admin panel
   - Check metrics: Win Rate, ROI, Max Drawdown, etc.
   - Click on "Trades" link to see individual trades

### Method 2: API (Programmatic)

#### Step 1: Get Authentication Token

```bash
# Login to get token
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'

# Response will include:
# {"access": "YOUR_ACCESS_TOKEN", "refresh": "YOUR_REFRESH_TOKEN"}
```

#### Step 2: Create Backtest

```bash
curl -X POST http://localhost:8000/api/backtest/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Backtest Test",
    "symbols": ["BTCUSDT"],
    "timeframe": "5m",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z",
    "strategy_params": {
      "long_rsi_min": 50,
      "long_rsi_max": 70,
      "sl_atr_multiplier": 1.5,
      "tp_atr_multiplier": 2.5
    },
    "initial_capital": 10000,
    "position_size": 100
  }'

# Response:
# {
#   "id": 2,
#   "status": "PENDING",
#   "message": "Backtest queued for execution",
#   "task_id": "abc-123-def-456"
# }
```

#### Step 3: Check Status

```bash
# List backtests
curl http://localhost:8000/api/backtest/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get specific backtest
curl http://localhost:8000/api/backtest/2/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get metrics
curl http://localhost:8000/api/backtest/2/metrics/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get trades
curl http://localhost:8000/api/backtest/2/trades/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Method 3: Python Script

```python
import requests
import time

# Configuration
BASE_URL = "http://localhost:8000"
EMAIL = "admin@example.com"
PASSWORD = "admin123"

# Login
response = requests.post(f"{BASE_URL}/api/auth/login/", json={
    "email": EMAIL,
    "password": PASSWORD
})
token = response.json()["access"]

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Create backtest
backtest_data = {
    "name": "Python Script Backtest",
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "timeframe": "1h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z",
    "strategy_params": {},
    "initial_capital": 10000,
    "position_size": 100
}

response = requests.post(
    f"{BASE_URL}/api/backtest/",
    headers=headers,
    json=backtest_data
)

backtest_id = response.json()["id"]
print(f"Backtest created: ID = {backtest_id}")

# Poll for completion
while True:
    response = requests.get(
        f"{BASE_URL}/api/backtest/{backtest_id}/",
        headers=headers
    )
    data = response.json()
    status = data["status"]
    print(f"Status: {status}")

    if status == "COMPLETED":
        print(f"Win Rate: {data['win_rate']}%")
        print(f"ROI: {data['roi']}%")
        print(f"Total Trades: {data['total_trades']}")
        break
    elif status == "FAILED":
        print(f"Error: {data.get('error_message')}")
        break

    time.sleep(5)  # Check every 5 seconds

# Get detailed metrics
response = requests.get(
    f"{BASE_URL}/api/backtest/{backtest_id}/metrics/",
    headers=headers
)
metrics = response.json()
print("\nMetrics:")
print(f"  Max Drawdown: {metrics['metrics']['max_drawdown_percentage']}%")
print(f"  Sharpe Ratio: {metrics['metrics']['sharpe_ratio']}")
print(f"  Profit Factor: {metrics['metrics']['profit_factor']}")
```

## Parameter Optimization

### Run Optimization

```bash
curl -X POST http://localhost:8000/api/optimization/run/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "RSI Optimization",
    "symbols": ["BTCUSDT"],
    "timeframe": "5m",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-03-31T23:59:59Z",
    "parameter_ranges": {
      "long_rsi_min": [45, 50, 55, 60],
      "long_rsi_max": [65, 70, 75, 80],
      "sl_atr_multiplier": [1.0, 1.5, 2.0],
      "tp_atr_multiplier": [2.0, 2.5, 3.0]
    },
    "search_method": "grid",
    "max_combinations": 100
  }'
```

### Get Best Parameters

```bash
# Get top 5 best parameter combinations
curl "http://localhost:8000/api/optimization/best/?top=5" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## AI Recommendations

### Generate Recommendations

```bash
curl -X POST http://localhost:8000/api/recommendations/generate/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lookback_days": 90,
    "min_samples": 10
  }'
```

### View Recommendations

```bash
# List all recommendations
curl http://localhost:8000/api/recommendations/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by status
curl "http://localhost:8000/api/recommendations/?status=PENDING" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Accept/Reject Recommendation

```bash
# Accept
curl -X POST http://localhost:8000/api/recommendations/1/accept/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Reject
curl -X POST http://localhost:8000/api/recommendations/1/reject/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"feedback_notes": "Not applicable for current market conditions"}'

# Mark as applied
curl -X POST http://localhost:8000/api/recommendations/1/apply/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Monitoring

### Check Celery Worker

```bash
# View logs
docker-compose logs -f celery-worker

# Check registered tasks
docker-compose exec celery-worker celery -A config inspect registered

# Check active tasks
docker-compose exec celery-worker celery -A config inspect active
```

### Check Backtest Status

```bash
# Via Django shell
docker-compose exec backend python manage.py shell

from signals.models_backtest import BacktestRun

# List all backtests
for bt in BacktestRun.objects.all():
    print(f"{bt.id}: {bt.name} - {bt.status}")

# Get specific backtest
bt = BacktestRun.objects.get(id=1)
print(f"Status: {bt.status}")
print(f"Win Rate: {bt.win_rate}%")
print(f"ROI: {bt.roi}%")
```

## Troubleshooting

### Issue: Backtest stays in PENDING status

**Causes:**
1. Celery worker not running
2. Celery worker not registering backtest tasks

**Solutions:**
```bash
# Restart Celery worker
docker-compose restart celery-worker

# Check worker is running
docker-compose ps celery-worker

# Check worker logs
docker-compose logs celery-worker --tail 100
```

### Issue: Historical data fetch fails

**Causes:**
1. Binance API rate limits
2. Invalid symbol names
3. Date range too large

**Solutions:**
- Use smaller date ranges (1-3 months at a time)
- Verify symbol names are correct (e.g., "BTCUSDT" not "BTC-USDT")
- Add delays between requests (already handled in code)

### Issue: No signals generated

**Causes:**
1. Strategy parameters too strict
2. No suitable trading conditions in historical data
3. Timeframe mismatch

**Solutions:**
- Loosen strategy parameters (e.g., wider RSI ranges)
- Test on different time periods
- Use different timeframes (5m, 15m, 1h, 4h)

### Issue: API authentication fails

**Solutions:**
```bash
# Create superuser if needed
docker-compose exec backend python manage.py createsuperuser

# Or use existing admin account:
# Username: admin
# Password: admin123
```

## Performance Tips

1. **Start Small**
   - Test with 1-2 symbols first
   - Use 1-7 day date ranges initially
   - Verify results before scaling up

2. **Optimize Parameters Carefully**
   - Start with 3-4 values per parameter
   - Use random search for >100 combinations
   - Monitor Celery worker memory usage

3. **Use Appropriate Timeframes**
   - 5m: For day trading strategies (large data volume)
   - 1h: For swing trading (balanced)
   - 4h/1d: For position trading (less data)

4. **Monitor Resources**
   ```bash
   # Check Docker container resources
   docker stats

   # Check database size
   docker-compose exec postgres psql -U postgres -d binance_bot -c "SELECT pg_size_pretty(pg_database_size('binance_bot'));"
   ```

## Example Workflows

### Workflow 1: Basic Strategy Testing

1. Create backtest with default parameters (1 month, 1 symbol)
2. Review results in admin panel
3. If promising, test on longer period (3-6 months)
4. Test on multiple symbols
5. Run optimization to fine-tune parameters

### Workflow 2: Parameter Optimization

1. Define parameter ranges (3-5 values each)
2. Run optimization (grid search, 1-3 months)
3. Review top 5 results
4. Select best parameters
5. Run full backtest with best parameters (6-12 months)
6. Verify consistency across multiple symbols

### Workflow 3: AI-Powered Improvement

1. Run 10+ optimizations with different settings
2. Generate AI recommendations
3. Review recommendations (sorted by confidence)
4. Apply high-confidence suggestions
5. Run new backtests to verify improvement
6. Iterate based on results

## Next Steps

1. ✅ **System is ready** - All components working
2. 📊 **Run your first backtest** - Use admin panel or API
3. 🔍 **Analyze results** - Review metrics and trades
4. ⚙️ **Optimize parameters** - Find best settings
5. 🤖 **Use AI recommendations** - Let the system learn
6. 🎨 **(Optional) Build frontend dashboard** - Visual interface

## Support

For issues or questions:
1. Check logs: `docker-compose logs backend celery-worker`
2. Review documentation: [BACKTESTING_SYSTEM_COMPLETE.md](BACKTESTING_SYSTEM_COMPLETE.md)
3. Test system: Run `backend/test_backtesting.py`

---

**Status**: ✅ Fully Operational
**Last Updated**: 2025-10-30
