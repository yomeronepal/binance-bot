# ML-Based Parameter Tuning - Test Scripts

This directory contains test scripts to run and verify the ML-based parameter optimization feature.

---

## Quick Start

### For Linux/Mac (Bash):

```bash
# Make script executable
chmod +x test_mltuning.sh

# Run the test
./test_mltuning.sh
```

### For Windows (Command Prompt):

```cmd
# Run the test
test_mltuning.bat
```

### For Windows (Git Bash):

```bash
# Run the bash script
bash test_mltuning.sh
```

---

## What the Test Script Does

The script performs a complete end-to-end test of the ML tuning feature:

1. **Generates JWT Token** - Authenticates with the API
2. **Creates ML Tuning Job** - Submits configuration with 50 training samples
3. **Monitors Execution** - Polls status every 10 seconds with progress updates
4. **Fetches Results** - Displays model quality, best parameters, and predictions
5. **Shows Feature Importance** - Lists top 10 most important parameters

---

## Test Configuration

The test uses the following parameters (from `test_mltuning_quick.json`):

```json
{
  "name": "Quick Test - ML Tuning",
  "symbols": ["BTCUSDT"],
  "timeframe": "5m",
  "training_start_date": "2024-01-01T00:00:00Z",
  "training_end_date": "2024-01-15T23:59:59Z",
  "test_start_date": "2024-01-16T00:00:00Z",
  "test_end_date": "2024-01-22T23:59:59Z",
  "ml_algorithm": "RANDOM_FOREST",
  "optimization_metric": "SHARPE_RATIO",
  "parameter_space": {
    "rsi_oversold": {"min": 25, "max": 35},
    "rsi_overbought": {"min": 65, "max": 75},
    "adx_min": {"min": 18, "max": 25},
    "volume_multiplier": {"min": 1.0, "max": 1.5}
  },
  "num_training_samples": 50,
  "sampling_method": "latin_hypercube",
  "hyperparameters": {
    "n_estimators": 100,
    "max_depth": 6
  },
  "initial_capital": 10000,
  "position_size": 100
}
```

**Training Period**: 2 weeks (Jan 1-15, 2024)
**Test Period**: 1 week (Jan 16-22, 2024)
**Samples**: 50 parameter combinations
**Algorithm**: Random Forest (faster than XGBoost for testing)

---

## Expected Output

### Successful Test

```
========================================
ML Tuning Test
========================================

[1/5] Generating JWT token...
✓ Token generated

[2/5] Creating ML tuning job...
✓ ML tuning job created (ID: 1)
  Task ID: abc123-def456-789...

[3/5] Monitoring execution...
This may take 5-15 minutes depending on number of samples...

Status: RUNNING | Progress: 0/50 (0%) | Time: 10s
Status: RUNNING | Progress: 25/50 (50%) | Time: 180s
Status: RUNNING | Progress: 50/50 (100%) | Time: 350s

✓ ML tuning job completed!

[4/5] Fetching results...
═══════════════════════════════════════
      ML TUNING RESULTS
═══════════════════════════════════════
ID:              1
Name:            Quick Test - ML Tuning
Status:          COMPLETED
ML Algorithm:    RANDOM_FOREST
Metric:          SHARPE_RATIO
Symbols:         BTCUSDT
Timeframe:       5m
Training Period: 2024-01-01 to 2024-01-15

--- Training Results ---
Samples:         50/50
R² Score:        0.7523
Validation R²:   0.6845
Overfitting:     0.0678

--- Best Parameters Found ---
  rsi_oversold: 28.5
  rsi_overbought: 71.2
  adx_min: 22.3
  volume_multiplier: 1.35

Predicted Performance: 2.15

--- Out-of-Sample Validation ---
ROI:             +8.45%
Sharpe Ratio:    1.92
Win Rate:        62.5%

--- Model Quality ---
Quality Score:   85.3/100
Production Ready: YES

Execution Time:  350.2s
═══════════════════════════════════════

[5/5] Fetching feature importance...
Top 10 Most Important Features:
   1. rsi_overbought          ██████████████████████████ 0.2850
   2. adx_min                 ████████████████████ 0.2245
   3. volume_multiplier       ███████████████ 0.1735
   4. rsi_oversold            ████████████ 0.1420
   5. rsi_range               ████████ 0.0985
   6. risk_reward_ratio       █████ 0.0565
   7. hour_sin                ██ 0.0200

═══════════════════════════════════════

Test completed successfully!

View in browser:
  Summary:       http://localhost:8000/api/mltuning/1/summary/
  Feature Imp:   http://localhost:8000/api/mltuning/1/feature_importance/
  Sensitivity:   http://localhost:8000/api/mltuning/1/sensitivity/
  Samples:       http://localhost:8000/api/mltuning/1/samples/
  Admin:         http://localhost:8000/admin/signals/mltuningjob/1/change/
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

5. **ML tuning task is registered:**
   ```bash
   docker-compose exec celery-worker celery -A config inspect registered | grep mltuning
   # Should show: scanner.tasks.mltuning_tasks.run_ml_tuning_async
   ```

6. **ML dependencies are installed:**
   The backend container should have: scikit-learn, xgboost, joblib, scipy

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

### Error: "Failed to create ML tuning job"

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

3. Check if ML tuning task is registered:
   ```bash
   docker-compose exec celery-worker celery -A config inspect registered | grep mltuning
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

### Error: "ModuleNotFoundError: No module named 'joblib'"

**Cause**: ML dependencies not installed in container

**Fix**:
1. Rebuild backend and celery-worker:
   ```bash
   docker-compose build backend celery-worker
   docker-compose up -d
   ```

2. Verify joblib is installed:
   ```bash
   docker-compose exec backend python -c "import joblib; print(joblib.__version__)"
   ```

---

### Error: "Timeout reached"

**Cause**: Task is taking longer than expected (15 minutes timeout)

**Solution**: This can happen with many samples. Check:
1. Celery worker logs: `docker-compose logs celery-worker --tail 100`
2. Check if task failed: `curl http://localhost:8000/api/mltuning/{ID}/`
3. Increase timeout in script if needed

---

### Low model quality score

**This is NORMAL** when:
- Training data insufficient or poor quality
- Parameter space too wide or poorly defined
- Test period doesn't match training period market conditions
- Hyperparameters not optimized

**Not a bug - it means more tuning is needed!**

To improve quality:
- Increase number of training samples (100-500)
- Use longer training period with varied market conditions
- Narrow parameter space around known good values
- Try different ML algorithms (XGBoost usually performs best)
- Tune hyperparameters (learning_rate, max_depth, n_estimators)

---

## Understanding Results

### Training Metrics

- **R² Score (Training)**: How well model fits training data (0-1, higher is better)
  - >0.7: Excellent
  - 0.5-0.7: Good
  - <0.5: Poor - need more samples or better features

- **R² Score (Validation)**: How well model generalizes to unseen data
  - Should be close to training R² (within 0.1-0.2)

- **Overfitting Score**: Difference between training and validation R²
  - <0.1: Minimal overfitting - excellent
  - 0.1-0.2: Some overfitting - acceptable
  - >0.2: Significant overfitting - model may not generalize

### Best Parameters

The optimal parameter combination found by the ML model that maximizes the optimization metric (Sharpe Ratio, ROI, etc.).

**Important**: These are ML predictions - always validate with:
1. Out-of-sample backtest
2. Walk-forward analysis
3. Paper trading

### Predicted Performance

What the ML model predicts the Sharpe Ratio (or other metric) will be with the best parameters.

### Out-of-Sample Validation

**Critical**: Tests the best parameters on completely unseen data (test period).

- **ROI**: Actual return in test period
- **Sharpe Ratio**: Risk-adjusted return
- **Win Rate**: % of profitable trades

If out-of-sample metrics are close to predicted performance, the model is reliable!

### Model Quality Score

**Scoring System (0-100)**:
- **80-100**: PRODUCTION READY - Safe to paper trade
- **60-79**: MODERATE - Needs more validation
- **0-59**: NOT READY - Do not use

**Criteria**:
1. Validation R² > 0.5 (30 pts)
2. Overfitting < 0.2 (25 pts)
3. Training R² > 0.6 (20 pts)
4. Out-of-sample ROI positive (15 pts)
5. Feature importance reasonable (10 pts)

### Feature Importance

Shows which parameters have the most impact on performance.

High importance (>0.20):
- These parameters are critical - optimize carefully
- Small changes have big impact on results

Medium importance (0.10-0.20):
- Important but less sensitive
- Good candidates for optimization

Low importance (<0.10):
- Minor impact - can use default values
- May be removed to simplify strategy

**Auto-generated features**:
- `rsi_range`: rsi_overbought - rsi_oversold
- `risk_reward_ratio`: tp_atr_multiplier / sl_atr_multiplier
- Market features (volatility, trend) if enabled
- Temporal features (hour, day) if enabled

---

## Performance Notes

**Typical Execution Times:**

| Samples | Training Period | Algorithm | Symbols | Time Estimate |
|---------|----------------|-----------|---------|---------------|
| 50 | 2 weeks | Random Forest | 1 | 5-8 min |
| 100 | 1 month | Random Forest | 1 | 10-15 min |
| 200 | 1 month | XGBoost | 1 | 20-30 min |
| 500 | 3 months | XGBoost | 1 | 60-90 min |
| 100 | 1 month | Neural Network | 1 | 15-25 min |

**Factors affecting performance:**
- Number of training samples (biggest factor - linear scaling)
- Training period length (more candles = slower backtests)
- ML algorithm (Neural Network slowest, Random Forest fastest)
- Number of symbols
- Timeframe (lower = more candles = slower)
- Historical data availability
- Binance API rate limits
- Server resources (CPU, memory)

**Optimization tips:**
- Start with 50-100 samples for initial testing
- Use Random Forest for quick iterations
- Switch to XGBoost for production (better accuracy)
- Use Latin Hypercube Sampling (default) for better space coverage
- Narrow parameter space based on feature importance

---

## Comparing Testing Methods

| Feature | Backtest | Walk-Forward | Monte Carlo | ML Tuning |
|---------|----------|--------------|-------------|-----------|
| **Purpose** | Quick test | Time consistency | Robustness | Optimal params |
| **Data** | Single period | Multiple windows | Same data, varied params | Train/val/test split |
| **Execution** | Seconds | Minutes | Minutes | Minutes-Hours |
| **Parameters** | Fixed | Fixed | Randomized | ML-optimized |
| **Overfitting Risk** | High | Medium | Low | **Lowest** |
| **Confidence** | Low | Medium | High | **Highest** |
| **Output** | Single result | Consistency score | Probability dist | Best params + quality |
| **Best For** | Iteration | Production readiness | Risk assessment | **Optimization** |

**Recommendation**:
1. Use **Backtest** for quick strategy testing and iteration
2. Use **ML Tuning** to find optimal parameters (this feature!)
3. Use **Monte Carlo** to assess robustness of ML-tuned parameters
4. Use **Walk-Forward** for final validation over time
5. All four together provide comprehensive validation

**ML Tuning Workflow**:
```
1. Initial Backtest → Get baseline performance
2. ML Tuning → Find optimal parameters
3. Monte Carlo → Test robustness of ML params
4. Walk-Forward → Validate consistency over time
5. Paper Trade → Real-world validation
6. Live Trade → Production deployment
```

---

## API Endpoints

All ML tuning endpoints:

```
POST   /api/mltuning/                        # Create new ML tuning job
GET    /api/mltuning/                        # List all jobs
GET    /api/mltuning/:id/                    # Get job details
DELETE /api/mltuning/:id/                    # Delete job
GET    /api/mltuning/:id/samples/            # Get training samples
GET    /api/mltuning/:id/feature_importance/ # Get feature importance
GET    /api/mltuning/:id/sensitivity/        # Get parameter sensitivity
POST   /api/mltuning/:id/predict/            # Predict for new parameters
POST   /api/mltuning/:id/find_optimal/       # Find optimal parameters
POST   /api/mltuning/:id/retry/              # Retry failed job
GET    /api/mltuning/:id/summary/            # Get quick summary

GET    /api/mlmodels/                        # List saved models
POST   /api/mlmodels/                        # Save model
GET    /api/mlmodels/:id/                    # Get model details
DELETE /api/mlmodels/:id/                    # Delete model
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

### 2. Create ML Tuning Job:

```bash
curl -X POST http://localhost:8000/api/mltuning/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d @test_mltuning_quick.json
```

### 3. Check Status:

```bash
curl http://localhost:8000/api/mltuning/1/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 4. Get Summary:

```bash
curl http://localhost:8000/api/mltuning/1/summary/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 5. Get Feature Importance:

```bash
curl http://localhost:8000/api/mltuning/1/feature_importance/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 6. Get Parameter Sensitivity:

```bash
curl http://localhost:8000/api/mltuning/1/sensitivity/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  | python -m json.tool
```

### 7. Predict Performance for New Parameters:

```bash
curl -X POST http://localhost:8000/api/mltuning/1/predict/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "rsi_oversold": 28,
      "rsi_overbought": 72,
      "adx_min": 22,
      "volume_multiplier": 1.3
    }
  }' | python -m json.tool
```

### 8. Find Optimal Parameters (Search Space):

```bash
curl -X POST http://localhost:8000/api/mltuning/1/find_optimal/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "num_candidates": 10000,
    "top_n": 10
  }' | python -m json.tool
```

---

## Customizing the Test

To test with different parameters, edit `test_mltuning.json` or create a new config:

```json
{
  "name": "Production ML Tuning - Multi-Symbol",
  "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "timeframe": "15m",
  "training_start_date": "2024-01-01T00:00:00Z",
  "training_end_date": "2024-06-30T23:59:59Z",
  "test_start_date": "2024-07-01T00:00:00Z",
  "test_end_date": "2024-07-31T23:59:59Z",
  "ml_algorithm": "GRADIENT_BOOSTING",
  "optimization_metric": "SHARPE_RATIO",
  "parameter_space": {
    "rsi_oversold": {"min": 20, "max": 35},
    "rsi_overbought": {"min": 65, "max": 80},
    "adx_min": {"min": 15, "max": 30},
    "volume_multiplier": {"min": 1.0, "max": 2.0},
    "min_confidence": {"min": 0.5, "max": 0.85},
    "sl_atr_multiplier": {"min": 1.0, "max": 2.5},
    "tp_atr_multiplier": {"min": 2.0, "max": 4.0}
  },
  "num_training_samples": 500,
  "sampling_method": "latin_hypercube",
  "hyperparameters": {
    "n_estimators": 300,
    "max_depth": 10,
    "learning_rate": 0.05
  },
  "feature_engineering": {
    "include_interactions": true,
    "include_market_conditions": true,
    "include_temporal_features": true
  },
  "initial_capital": 50000,
  "position_size": 500
}
```

Then run:
```bash
CONFIG_FILE=test_mltuning.json ./test_mltuning.sh
# Or on Windows:
set CONFIG_FILE=test_mltuning.json && test_mltuning.bat
```

---

## ML Algorithms

### Random Forest (RANDOM_FOREST)
- **Speed**: Fast ⚡⚡⚡
- **Accuracy**: Good ★★★☆☆
- **Best For**: Quick testing, initial exploration
- **Pros**: Fast training, handles non-linear relationships well
- **Cons**: Can overfit with too many trees

### Gradient Boosting (GRADIENT_BOOSTING / XGBoost)
- **Speed**: Medium ⚡⚡☆
- **Accuracy**: Excellent ★★★★★
- **Best For**: Production use, best results
- **Pros**: Highest accuracy, best generalization
- **Cons**: Slower than Random Forest, more hyperparameters

### Neural Network (NEURAL_NETWORK)
- **Speed**: Slow ⚡☆☆
- **Accuracy**: Good ★★★★☆
- **Best For**: Complex non-linear relationships, large datasets
- **Pros**: Can learn very complex patterns
- **Cons**: Slowest, needs more data, harder to tune

### Support Vector Regression (SVR)
- **Speed**: Medium ⚡⚡☆
- **Accuracy**: Good ★★★★☆
- **Best For**: Small datasets, smooth relationships
- **Pros**: Works well with fewer samples
- **Cons**: Slow with large datasets, sensitive to scaling

### Ensemble (ENSEMBLE)
- **Speed**: Slowest ⚡☆☆
- **Accuracy**: Best ★★★★★
- **Best For**: Maximum accuracy, critical decisions
- **Pros**: Combines multiple models for best results
- **Cons**: Very slow, high computational cost

**Recommendation**:
- Testing/Development: **Random Forest**
- Production: **Gradient Boosting (XGBoost)**
- Maximum Accuracy: **Ensemble**

---

## Optimization Metrics

### SHARPE_RATIO (Recommended)
- Risk-adjusted returns
- Balances profit and volatility
- Best for consistent, stable strategies

### ROI (Total Return)
- Simple profit percentage
- Good for aggressive strategies
- Doesn't account for risk

### WIN_RATE
- Percentage of winning trades
- Good for high-frequency strategies
- Ignores profit size

### PROFIT_FACTOR
- Gross profit / Gross loss
- Accounts for both win rate and profit size
- Good all-around metric

### MAX_DRAWDOWN (Minimize)
- Largest peak-to-trough decline
- Good for risk-averse strategies
- Focuses on downside protection

---

## Next Steps

After successful ML tuning:

1. **Analyze Feature Importance**: Understand what drives performance
2. **Test Parameter Sensitivity**: See how sensitive results are to each parameter
3. **Validate with Monte Carlo**: Run Monte Carlo on ML-tuned parameters
4. **Walk-Forward Test**: Validate consistency over time
5. **Paper Trade**: Test in real-time with paper account
6. **Save Model**: Save successful models for future use
7. **Refine Parameter Space**: Narrow ranges based on feature importance
8. **Iterate**: Re-run ML tuning with refined space
9. **Live Trade**: Deploy only models with quality score ≥80

---

## Advanced Usage

### Saving Trained Models

After successful training, save the model for reuse:

```bash
curl -X POST http://localhost:8000/api/mlmodels/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Model - BTCUSDT",
    "tuning_job": 1,
    "is_active": true,
    "notes": "Validated on 6 months data, quality score 85"
  }'
```

### Using Saved Models for Predictions

Once saved, you can make predictions without retraining:

```bash
curl -X POST http://localhost:8000/api/mltuning/1/predict/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "rsi_oversold": 30,
      "rsi_overbought": 70,
      "adx_min": 20
    }
  }'
```

### Hyperparameter Tuning

Different ML algorithms have different hyperparameters:

**Random Forest**:
```json
{
  "n_estimators": 100-500,  // Number of trees
  "max_depth": 5-20,        // Tree depth (prevent overfitting)
  "min_samples_split": 2-10 // Min samples to split node
}
```

**XGBoost**:
```json
{
  "n_estimators": 100-500,    // Number of boosting rounds
  "max_depth": 3-10,          // Tree depth
  "learning_rate": 0.01-0.3,  // Step size (lower = more stable)
  "subsample": 0.6-1.0,       // Sample fraction per tree
  "min_child_weight": 1-10    // Minimum sum of weights in child
}
```

**Neural Network**:
```json
{
  "hidden_layers": [64, 32], // Layer sizes
  "activation": "relu",       // Activation function
  "learning_rate": 0.001,     // Training step size
  "epochs": 100,              // Training iterations
  "batch_size": 32            // Samples per gradient update
}
```

---

## Support

For issues or questions:
1. Check documentation: `docs/ML_TUNING_HOW_IT_WORKS.md`
2. Check Celery logs: `docker-compose logs celery-worker`
3. Check backend logs: `docker-compose logs backend`
4. Verify task registration: `celery inspect registered | grep mltuning`
5. Check ML dependencies: `docker-compose exec backend python -c "import sklearn, xgboost, joblib; print('OK')"`

---

**Last Updated**: 2025-10-30
**Status**: ✅ Ready for Testing
**Test Scripts**: `test_mltuning.sh`, `test_mltuning.bat`
**Quick Test**: `test_mltuning_quick.json` (50 samples, ~5-8 min)
**Full Test**: `test_mltuning.json` (200 samples, ~20-30 min)
