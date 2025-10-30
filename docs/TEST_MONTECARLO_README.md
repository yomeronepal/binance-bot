# Monte Carlo Simulation - Test Scripts

This directory contains test scripts to run and verify the Monte Carlo simulation feature.

---

## Quick Start

### For Linux/Mac (Bash):

```bash
# Make script executable
chmod +x test_montecarlo.sh

# Run the test
./test_montecarlo.sh
```

### For Windows (Command Prompt):

```cmd
# Run the test
test_montecarlo.bat
```

### For Windows (Git Bash):

```bash
# Run the bash script
bash test_montecarlo.sh
```

---

## What the Test Script Does

The script performs a complete end-to-end test of the Monte Carlo simulation feature:

1. **Generates JWT Token** - Authenticates with the API
2. **Creates Monte Carlo Simulation** - Submits configuration with 100 simulations
3. **Monitors Execution** - Polls status every 5 seconds with progress updates
4. **Fetches Results** - Displays comprehensive statistical analysis
5. **Shows Best/Worst Runs** - Lists top 5 best and worst performing runs

---

## Test Configuration

The test uses the following parameters (from `test_montecarlo.json`):

```json
{
  "name": "Test Monte Carlo - BTCUSDT Robustness",
  "symbols": ["BTCUSDT"],
  "timeframe": "5m",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-02-01T23:59:59Z",
  "num_simulations": 100,
  "strategy_params": {
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "adx_min": 20,
    "volume_multiplier": 1.2,
    "min_confidence": 0.7
  },
  "randomization_config": {
    "rsi_oversold": {"min": 25, "max": 35, "type": "uniform"},
    "rsi_overbought": {"min": 65, "max": 75, "type": "uniform"},
    "adx_min": {"min": 15, "max": 25, "type": "uniform"},
    "volume_multiplier": {"min": 1.0, "max": 1.5, "type": "uniform"},
    "min_confidence": {"min": 0.6, "max": 0.8, "type": "uniform"}
  },
  "initial_capital": 10000,
  "position_size": 100
}
```

**Test Period**: January 2024 (1 month)
**Simulations**: 100 runs with randomized parameters
**Strategy**: RSI + ADX + Volume-based signals

---

## Expected Output

### Successful Test

```
========================================
Monte Carlo Simulation Test
========================================

[1/5] Generating JWT token...
✓ Token generated

[2/5] Creating Monte Carlo simulation...
✓ Monte Carlo simulation created (ID: 1)

[3/5] Monitoring execution...
This may take 1-5 minutes depending on number of simulations...

Status: RUNNING | Progress: 0/100 (0%) | Time: 5s
Status: RUNNING | Progress: 50/100 (50%) | Time: 60s
Status: COMPLETED | Progress: 100/100 (100%) | Time: 120s

✓ Monte Carlo simulation completed!

[4/5] Fetching results...
═══════════════════════════════════════
      MONTE CARLO RESULTS
═══════════════════════════════════════
ID:              1
Name:            Test Monte Carlo - BTCUSDT Robustness
Status:          COMPLETED
Symbols:         BTCUSDT
Timeframe:       5m
Period:          2024-01-01 to 2024-02-01
Simulations:     100/100

--- Statistical Results ---
Expected Return: +5.23%
Median Return:   +4.85%
Std Deviation:   2.15%
Best Case:       +12.45%
Worst Case:      -1.35%

--- Confidence Intervals ---
95% Confidence:  [2.15%, 8.42%]
99% Confidence:  [1.05%, 10.15%]

--- Probability Metrics ---
Prob of Profit:  72.0%
Prob of Loss:    28.0%

--- Risk Metrics ---
VaR at 95%:      1.85%
VaR at 99%:      3.25%
Mean Drawdown:   3.45%
Worst Drawdown:  8.25%

--- Performance Metrics ---
Mean Sharpe:     1.85
Mean Win Rate:   58.5%

--- Robustness Assessment ---
Robust:          YES
Score:           85/100
Label:           STATISTICALLY ROBUST
═══════════════════════════════════════

[5/5] Fetching best/worst runs...
Best 5 Runs:
  Run #42: ROI +12.45%, Win Rate 65.2%, Sharpe 2.35
  Run #18: ROI +10.85%, Win Rate 63.5%, Sharpe 2.15
  Run #73: ROI +9.95%, Win Rate 61.8%, Sharpe 2.05
  Run #29: ROI +9.45%, Win Rate 60.5%, Sharpe 1.95
  Run #56: ROI +8.85%, Win Rate 59.2%, Sharpe 1.85

Worst 5 Runs:
  Run #91: ROI -1.35%, Win Rate 45.5%, Sharpe 0.25
  Run #12: ROI -0.85%, Win Rate 47.2%, Sharpe 0.35
  Run #67: ROI -0.45%, Win Rate 48.5%, Sharpe 0.45
  Run #38: ROI +0.15%, Win Rate 49.5%, Sharpe 0.55
  Run #84: ROI +0.55%, Win Rate 50.2%, Sharpe 0.65

═══════════════════════════════════════

Test completed successfully!

View in browser:
  Summary:       http://localhost:8000/api/montecarlo/1/summary/
  All Runs:      http://localhost:8000/api/montecarlo/1/runs/
  Distributions: http://localhost:8000/api/montecarlo/1/distributions/
  Admin:         http://localhost:8000/admin/signals/montecarlosimulation/1/change/
```

---

## Prerequisites

Before running the test script, ensure:

1. **Docker services are running:**
   ```bash
   docker-compose ps
   # Should show: backend, celery-worker, postgres, redis all running
   ```

2. **Backend is accessible:**
   ```bash
   curl http://localhost:8000/api/health/
   # Should return: {"status": "healthy"}
   ```

3. **User account exists:**
   ```bash
   docker-compose exec backend python manage.py createsuperuser
   ```

4. **Celery worker is listening to backtesting queue:**
   ```bash
   docker-compose exec celery-worker celery -A config inspect active_queues | grep backtesting
   # Should show the backtesting queue
   ```

5. **Monte Carlo task is registered:**
   ```bash
   docker-compose exec celery-worker celery -A config inspect registered | grep montecarlo
   # Should show: scanner.tasks.montecarlo_tasks.run_montecarlo_simulation_async
   ```

---

## Troubleshooting

### Error: "Failed to generate token"

**Cause**: No user exists in the database

**Fix**:
```bash
docker-compose exec backend python manage.py createsuperuser
# Follow prompts to create admin user
```

---

### Error: "Failed to create Monte Carlo simulation"

**Cause**: Backend not accessible or authentication failed

**Fix**:
1. Check backend is running: `docker-compose ps backend`
2. Check backend logs: `docker-compose logs backend --tail 50`
3. Verify API is accessible: `curl http://localhost:8000/api/health/`

---

### Status stays "PENDING" forever

**Cause**: Celery worker not picking up tasks

**Fix**:
1. Check Celery worker is running:
   ```bash
   docker-compose ps celery-worker
   ```

2. Check Celery is listening to backtesting queue:
   ```bash
   docker-compose exec celery-worker celery -A config inspect active_queues
   ```

3. Check if Monte Carlo task is registered:
   ```bash
   docker-compose exec celery-worker celery -A config inspect registered | grep montecarlo
   ```

4. Check Celery logs for errors:
   ```bash
   docker-compose logs celery-worker --tail 100
   ```

5. If backtesting queue is missing, restart services:
   ```bash
   docker-compose restart backend celery-worker
   ```

---

### Error: "Timeout reached"

**Cause**: Task is taking longer than expected (10 minutes timeout)

**Solution**: This is unusual for 100 simulations. Check:
1. Celery worker logs: `docker-compose logs celery-worker --tail 100`
2. Check if task failed: `curl http://localhost:8000/api/montecarlo/{ID}/`
3. Increase timeout in script if needed

---

### Simulation shows low robustness score

**This is NORMAL** when:
- Test data has insufficient volatility
- Parameter ranges are too wide
- Test period too short
- Strategy not optimized for the market conditions

**Not a bug - it means the strategy needs improvement!**

To improve robustness:
- Adjust strategy parameters based on parameter impact analysis
- Narrow randomization ranges around optimal values
- Test on longer periods with varied market conditions
- Optimize stop loss and take profit levels

---

## Understanding Results

### Statistical Metrics

- **Expected Return (Mean)**: Average ROI across all simulations - what you can "expect" on average
- **Median Return**: Middle value - less affected by outliers than mean
- **Std Deviation**: How much returns vary - higher = more risk
- **Best/Worst Case**: Extreme outcomes to understand range of possibilities

### Confidence Intervals

- **95% CI**: 95% of future outcomes should fall within this range
- **99% CI**: 99% of future outcomes should fall within this range
- Narrower intervals = more consistent strategy

### Probability Metrics

- **Probability of Profit**: % chance of making money
  - >70%: Excellent
  - 60-70%: Good
  - <60%: Weak
- **Probability of Loss**: % chance of losing money

### Risk Metrics

- **VaR (Value at Risk)**: Maximum expected loss at given confidence level
  - Example: VaR 95% = 2% means you have a 5% chance of losing more than 2%
- **Drawdown**: Peak-to-trough decline
  - Mean: Average worst drawdown across all runs
  - Worst Case: Largest drawdown observed

### Robustness Score

**Scoring System (0-100)**:
- **80-100**: STATISTICALLY ROBUST - Safe to deploy
- **60-79**: MODERATELY ROBUST - Use with caution
- **0-59**: NOT ROBUST - Do not deploy

**Criteria**:
1. Positive expected return (30 pts)
2. High probability of profit >70% (25 pts)
3. Good Sharpe ratio >1.5 (25 pts)
4. Limited downside risk VaR<10% (20 pts)
5. Consistent returns CV<1.0 (20 pts)

---

## Performance Notes

**Typical Execution Times:**

| Simulations | Period | Timeframe | Symbols | Time Estimate |
|-------------|--------|-----------|---------|---------------|
| 10 | 2 weeks | 5m | 1 | 30-60s |
| 100 | 1 month | 5m | 1 | 3-5 min |
| 1000 | 1 month | 5m | 1 | 30-50 min |
| 100 | 3 months | 5m | 1 | 10-15 min |
| 100 | 1 month | 5m | 3 | 10-15 min |

**Factors affecting performance:**
- Number of simulations (linear scaling)
- Test period length
- Number of symbols
- Timeframe (lower = more candles)
- Historical data availability
- Binance API rate limits
- Server resources

---

## Comparing Testing Methods

| Feature | Backtest | Walk-Forward | Monte Carlo |
|---------|----------|--------------|-------------|
| **Purpose** | Quick testing | Validate consistency | Statistical robustness |
| **Data** | Single period | Multiple windows | Same period, varied params |
| **Execution** | Seconds | Minutes | Minutes |
| **Overfitting Risk** | High | Medium | Low |
| **Confidence** | Low | Medium | **High** |
| **Output** | Single result | Consistency score | Probability distribution |
| **Best For** | Iteration | Production readiness | Risk assessment |

**Recommendation**:
1. Use **Backtest** for quick strategy testing and iteration
2. Use **Walk-Forward** for validating consistency over time
3. Use **Monte Carlo** for understanding risk and statistical robustness
4. All three together provide comprehensive validation

---

## API Endpoints

All Monte Carlo endpoints:

```
POST   /api/montecarlo/                        # Create new simulation
GET    /api/montecarlo/                        # List all simulations
GET    /api/montecarlo/:id/                    # Get simulation details
DELETE /api/montecarlo/:id/                    # Delete simulation
GET    /api/montecarlo/:id/runs/               # Get all simulation runs
GET    /api/montecarlo/:id/distributions/      # Get distribution data
GET    /api/montecarlo/:id/summary/            # Get quick summary
GET    /api/montecarlo/:id/best_worst_runs/    # Get best/worst runs
GET    /api/montecarlo/:id/parameter_impact/   # Parameter correlation analysis
POST   /api/montecarlo/:id/retry/              # Retry failed simulation
```

---

## Manual Testing (Without Script)

If you prefer to test manually:

### 1. Get JWT Token:

```bash
docker-compose exec backend python manage.py shell -c "
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
User = get_user_model()
user = User.objects.first()
refresh = RefreshToken.for_user(user)
print(str(refresh.access_token))
"
```

### 2. Create Monte Carlo Simulation:

```bash
curl -X POST http://localhost:8000/api/montecarlo/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d @test_montecarlo.json
```

### 3. Check Status:

```bash
curl http://localhost:8000/api/montecarlo/1/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 4. Get Summary:

```bash
curl http://localhost:8000/api/montecarlo/1/summary/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 5. Get Distributions:

```bash
curl http://localhost:8000/api/montecarlo/1/distributions/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 6. Get Best/Worst Runs:

```bash
curl http://localhost:8000/api/montecarlo/1/best_worst_runs/?n=10 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 7. Parameter Impact Analysis:

```bash
curl http://localhost:8000/api/montecarlo/1/parameter_impact/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

---

## Customizing the Test

To test with different parameters, edit `test_montecarlo.json`:

```json
{
  "name": "Custom Strategy Test",
  "symbols": ["ETHUSDT", "BNBUSDT"],
  "timeframe": "15m",
  "start_date": "2024-03-01T00:00:00Z",
  "end_date": "2024-06-30T23:59:59Z",
  "num_simulations": 500,
  "strategy_params": {
    "rsi_oversold": 25,
    "rsi_overbought": 75,
    "adx_min": 25,
    "volume_multiplier": 1.5
  },
  "randomization_config": {
    "rsi_oversold": {"min": 20, "max": 30, "type": "uniform"},
    "rsi_overbought": {"min": 70, "max": 80, "type": "uniform"}
  },
  "initial_capital": 50000,
  "position_size": 500
}
```

Then run:
```bash
./test_montecarlo.sh  # Or test_montecarlo.bat on Windows
```

---

## Quick Test

For a quick test with fewer simulations, use `test_montecarlo_quick.json`:

- **10 simulations** instead of 100
- **2 weeks** test period instead of 1 month
- Executes in ~30-60 seconds

---

## Parameter Randomization

### Supported Distribution Types

**Uniform** (equal probability across range):
```json
"rsi_oversold": {
  "min": 25,
  "max": 35,
  "type": "uniform"
}
```

**Normal** (bell curve around base value):
```json
"adx_min": {
  "min": 15,
  "max": 25,
  "type": "normal"
}
```

**Discrete** (integer values only):
```json
"lookback_period": {
  "min": 10,
  "max": 20,
  "type": "discrete"
}
```

---

## Next Steps

After successful testing:

1. **View in Admin Panel**: http://localhost:8000/admin/signals/montecarlosimulation/
2. **Try Different Periods**: Test on various market conditions
3. **Analyze Parameter Impact**: Use `/parameter_impact/` endpoint
4. **Compare Multiple Strategies**: Run Monte Carlo on different configurations
5. **Adjust Based on Results**: Optimize parameters based on correlations
6. **Validate with Walk-Forward**: Use walk-forward optimization for time-based validation
7. **Paper Trade**: Test validated strategies in paper trading mode
8. **Live Trade**: Deploy only strategies with robustness score ≥80

---

## Support

For issues or questions:
1. Check documentation: `docs/MONTE_CARLO_IMPLEMENTATION_COMPLETE.md`
2. Check Celery logs: `docker-compose logs celery-worker`
3. Check backend logs: `docker-compose logs backend`
4. Verify task registration: `celery inspect registered | grep montecarlo`

---

**Last Updated**: 2025-10-30
**Status**: ✅ Ready for Testing
**Test Scripts**: `test_montecarlo.sh`, `test_montecarlo.bat`
**Quick Test**: `test_montecarlo_quick.json`
