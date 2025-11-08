# Parameter Optimization Guide

Complete guide for running comprehensive parameter optimization tests on the trading bot.

---

## Overview

The parameter optimization script tests 9 different parameter configurations to find the optimal settings that maximize:
- **Win Rate**: Target 30%+ (currently ~25%)
- **ROI**: Target +0.5%+ (currently near 0%)
- **Profit Factor**: Target 1.15+ (currently ~1.0)

---

## Quick Start

### 1. Ensure CSV Data is Available

The optimization script uses local CSV data from `backend/backtest_data/`. Verify files exist:

```bash
# Windows
dir backend\backtest_data\low\BTCUSDT_4h.csv

# Linux/Mac
ls backend/backtest_data/low/BTCUSDT_4h.csv
```

Expected output: `BTCUSDT_4h.csv` should be present with ~6,500+ candles.

### 2. Run Optimization Script

```bash
# Navigate to backend directory
cd backend

# Run optimization (takes ~10-15 minutes)
python scripts/optimize_parameters_comprehensive.py
```

### 3. Review Results

Results are displayed in a table and saved to `backend/optimization_results.json`.

---

## What Gets Tested

### Baseline Configuration (CURRENT)
- **ADX**: 26/28 (already optimized by you)
- **RSI**: 23-33 / 67-77
- **SL/TP**: 1.5x / 5.25x ATR (1:3.5 R/R)
- **Confidence**: 73%

### Test Configurations

| Config | Test Focus | Hypothesis |
|--------|-----------|-----------|
| **OPT-1: Tighter RSI** | RSI 25-30 / 70-75 | Fewer but higher quality entries |
| **OPT-2: Wider RSI** | RSI 20-35 / 65-80 | More signals, rely on ADX filter |
| **OPT-3: High Confidence** | 76% confidence | Stricter quality filter |
| **OPT-4: Lower Confidence** | 70% confidence | More signals with ADX safety |
| **OPT-5: Wider Stops** | SL 2.0x, TP 6.0x | More breathing room, fewer stop-outs |
| **OPT-6: Better R/R** | TP 6.0x (1:4 R/R) | Lower breakeven win rate (20%) |
| **OPT-7: Quality Focus** | Tight RSI + High Conf + Wide Stops | Maximum quality approach |
| **OPT-8: Balanced** | Moderate all parameters | Balanced approach |

---

## Understanding the Results

### Results Table Format

```
Rank  Configuration           Score     ROI %     Win %     PF      Trades    P&L $
1     OPT-5: Wider Stops      45.23     ✅ 0.15   ⚠️ 28.5   1.12    7         $15.23
2     CURRENT (ADX 26/28)     42.10     ❌ -0.03  ❌ 16.7   0.95    6         -$3.12
```

**Column Meanings**:
- **Score**: Weighted score (0-100) combining all metrics
  - Win Rate: 40% weight
  - ROI: 30% weight
  - Profit Factor: 20% weight
  - Trade Frequency: 10% weight
- **ROI %**: Return on investment (✅ positive, ❌ negative)
- **Win %**: Winning trade percentage (✅ ≥30%, ⚠️ ≥25%, ❌ <25%)
- **PF**: Profit Factor (total wins / total losses)
- **Trades**: Total number of trades executed
- **P&L $**: Total profit/loss in dollars

### Winner Details

The script shows detailed metrics for the winning configuration:

```
🏆 WINNER: OPT-5: Wider Stops
─────────────────────────────────────────
Score: 45.23/100
Hypothesis: Wider stops = fewer premature stop-outs

Performance Metrics:
  ROI: 0.15%
  Win Rate: 28.5% (2W / 5L)
  Profit Factor: 1.12
  Total Trades: 7
  Average Win: $85.42
  Average Loss: -$32.15
  Max Drawdown: 3.2%
  Sharpe Ratio: 0.45
  Total P&L: $15.23
  Final Capital: $10,015.23

Winning Parameters:
  RSI Range (LONG): 23.0-33.0
  RSI Range (SHORT): 67.0-77.0
  ADX Min (LONG): 26.0
  ADX Min (SHORT): 28.0
  SL ATR: 2.0x
  TP ATR: 6.0x
  R/R Ratio: 1:3.0
  Min Confidence: 73%
```

---

## Interpreting Results

### Key Metrics to Watch

#### 1. Win Rate
- **Target**: 30%+
- **Current**: ~16.7% (CURRENT config)
- **Breakeven** (for 1:3.5 R/R): 22.2%

**What to look for**: Configurations that push win rate above 25% while maintaining good R/R ratio.

#### 2. ROI (Return on Investment)
- **Target**: +0.5% or higher
- **Current**: -0.03% (only $3.12 loss)
- **Status**: Very close to profitability

**What to look for**: Any positive ROI configuration is profitable. Prioritize consistency over high ROI.

#### 3. Profit Factor
- **Target**: 1.15+
- **Current**: ~0.95
- **Breakeven**: 1.0

**Formula**: Total Wins / Total Losses

**What to look for**: Values above 1.0 indicate profitability. Higher is better, but 1.15+ is excellent.

#### 4. Total Trades
- **Current**: 6 trades over 11 months
- **Target**: 6-10 trades (conservative strategy)

**What to look for**: Moderate trade frequency. Too few (<4) may be overly conservative, too many (>15) may be overly aggressive.

#### 5. Max Drawdown
- **Target**: <10%
- **Current**: Very low (~1-2%)

**What to look for**: Lower is safer. Drawdown >15% may be risky for live trading.

### Score Calculation

The optimization score combines multiple factors:

```python
score = (
    (win_rate / 35.0) * 100 * 0.4 +      # 40% weight
    ((roi + 5.0) / 10.0) * 100 * 0.3 +   # 30% weight
    (profit_factor / 1.5) * 100 * 0.2 +   # 20% weight
    (total_trades / 10.0) * 100 * 0.1     # 10% weight
)
```

**Perfect Score (100)**:
- Win Rate: 35%
- ROI: +5%
- Profit Factor: 1.5
- Trades: 10

---

## Common Optimization Outcomes

### Scenario 1: Wider Stops Win
**Result**: OPT-5 (Wider Stops) scores highest

**Interpretation**: Current stops (1.5x ATR) are too tight, causing premature stop-outs. Strategy needs more breathing room.

**Action**: Update [user_config.py](../backend/scanner/config/user_config.py):
```python
BINANCE_CONFIG = {
    "sl_atr_multiplier": 2.0,  # Changed from 1.5
    "tp_atr_multiplier": 6.0,  # Changed from 5.25
    # ... keep other parameters
}
```

### Scenario 2: Lower Confidence Wins
**Result**: OPT-4 (Lower Confidence 70%) scores highest

**Interpretation**: Current confidence threshold (73%) is too strict, filtering out profitable signals.

**Action**: Update user_config.py:
```python
BINANCE_CONFIG = {
    "min_confidence": 0.70,  # Changed from 0.73
    # ... keep other parameters
}
```

### Scenario 3: Tighter RSI Wins
**Result**: OPT-1 (Tighter RSI) scores highest

**Interpretation**: Current RSI range (23-33) is too wide, catching low-quality signals. Narrower range improves entry timing.

**Action**: Update user_config.py:
```python
BINANCE_CONFIG = {
    "long_rsi_min": 25.0,  # Changed from 23.0
    "long_rsi_max": 30.0,  # Changed from 33.0
    "short_rsi_min": 70.0,  # Changed from 67.0
    "short_rsi_max": 75.0,  # Changed from 77.0
    # ... keep other parameters
}
```

### Scenario 4: No Clear Winner
**Result**: All configs score similarly, CURRENT is competitive

**Interpretation**: ADX optimization (26/28) already did most of the work. Strategy is near-optimal, needs different approach.

**Action**: Consider Phase 2 enhancements:
- Multi-timeframe confirmation
- Trailing stop loss
- Partial profit taking

---

## After Finding Winner

### 1. Update Configuration

Edit [backend/scanner/config/user_config.py](../backend/scanner/config/user_config.py) with winning parameters.

### 2. Validate Configuration

```bash
# Test configuration is valid
python backend/scanner/config/user_config.py

# Expected output:
# ✅ BINANCE Configuration: VALID
# ✅ FOREX Configuration: VALID
# ✅ ALL CONFIGURATIONS VALID
```

### 3. Restart Services

```bash
# Using Docker Compose
docker-compose restart backend celery_worker celery_beat

# Or using shortcuts
make docker-restart          # Linux/Mac
run.bat docker-restart       # Windows
```

### 4. Monitor Live Performance

```bash
# Watch for new signals
docker logs -f binancebot_celery_worker | grep "New.*signal"

# Check signal generation
curl http://localhost:8000/api/signals/ | python -m json.tool
```

### 5. Run Extended Validation

```bash
# Run backtest with new parameters
cd backend
python scripts/test_extended_period.py
```

---

## Advanced Usage

### Test Single Configuration

Edit the script to test only one config:

```python
# In optimize_parameters_comprehensive.py

# Comment out all configs except the one you want
OPTIMIZATION_CONFIGS = [
    # Only test wider stops
    {
        "name": "OPT-5: Wider Stops",
        "params": {
            # ... parameters
        }
    },
]
```

### Test Different Symbol

```python
# In optimize_parameters_comprehensive.py

TEST_SYMBOL = "ETHUSDT"  # Change from BTCUSDT
```

### Test Different Timeframe

```python
# In optimize_parameters_comprehensive.py

TIMEFRAME = "1h"  # Change from 4h
```

### Test Different Period

```python
# In optimize_parameters_comprehensive.py

START_DATE = datetime(2024, 6, 1)   # Last 6 months
END_DATE = datetime(2024, 11, 30)
```

---

## Troubleshooting

### Issue: "No data loaded for BTCUSDT"

**Cause**: CSV file not found in backend/backtest_data/

**Solution**:
```bash
# Check if file exists
ls backend/backtest_data/low/BTCUSDT_4h.csv

# If missing, download data
cd backend
python scripts/data/download_long_period.py
```

### Issue: "Module not found" errors

**Cause**: Django not properly initialized

**Solution**:
```bash
# Ensure you're in backend/ directory
cd backend

# Run with proper Python environment
python scripts/optimize_parameters_comprehensive.py
```

### Issue: All configs return same results

**Cause**: Volatility-aware mode is enabled (overrides parameters)

**Solution**: Verify line 272 in optimization script:
```python
engine = SignalDetectionEngine(signal_config, use_volatility_aware=False)
```

Must be `False`, not `True`.

### Issue: No trades generated

**Cause**: Parameters too strict

**Solution**: Check if any config generates trades. If none do, test period may not have suitable market conditions. Try different dates or symbols.

---

## Expected Runtime

| Configurations | Estimated Time |
|---------------|---------------|
| 1 config | ~1-2 minutes |
| 9 configs (full) | ~10-15 minutes |
| 20+ configs | ~20-30 minutes |

**Factors affecting speed**:
- CSV file size (larger = slower)
- Number of candles (more = slower)
- Number of signals generated (more = slower)

---

## Output Files

### 1. Console Output
Real-time progress and results displayed in terminal.

### 2. optimization_results.json
```json
{
  "timestamp": "2025-11-06T10:30:00",
  "test_period": "2024-01-01 to 2024-11-30",
  "symbol": "BTCUSDT",
  "timeframe": "4h",
  "results": [
    {
      "config_name": "OPT-5: Wider Stops",
      "status": "SUCCESS",
      "score": 45.23,
      "metrics": {
        "roi": 0.15,
        "win_rate": 28.5,
        "profit_factor": 1.12,
        "total_trades": 7,
        ...
      },
      "parameters": {
        "long_rsi_min": 23.0,
        "sl_atr_multiplier": 2.0,
        ...
      }
    },
    ...
  ]
}
```

**Location**: `backend/optimization_results.json`

---

## Next Steps After Optimization

### Phase 1: Parameter Tuning (Current)
- ✅ ADX optimization (26/28)
- ✅ Comprehensive parameter testing
- ⏳ Apply winning configuration
- ⏳ Validate on extended period

### Phase 2: Strategy Enhancements
- Multi-timeframe confirmation
- Trailing stop loss
- Partial profit taking
- Risk management improvements

### Phase 3: Live Deployment
- Paper trading validation
- Live trading (small capital)
- Performance monitoring
- Continuous optimization

---

## Tips for Success

### 1. Start Conservative
Don't immediately deploy the highest-scoring config. Verify it makes sense:
- Check if trade count is reasonable (6-10 trades)
- Ensure parameters are logical (RSI min < max, TP > SL)
- Validate hypothesis matches results

### 2. Compare Multiple Metrics
Don't rely solely on score. Consider:
- Is ROI positive?
- Is win rate above breakeven?
- Is profit factor > 1.0?
- Is drawdown acceptable?

### 3. Test on Different Periods
After finding a winner, test it on different time periods:
- Last 3 months
- Last 6 months
- Full 11 months

Consistency across periods indicates robustness.

### 4. Document Everything
Keep track of:
- Which configs were tested
- Why certain parameters were chosen
- Results of each optimization run
- Changes made to production config

---

## Mathematical Reference

### Risk/Reward Ratios

| SL ATR | TP ATR | R/R Ratio | Breakeven Win Rate |
|--------|--------|-----------|-------------------|
| 1.5x | 5.25x | 1:3.5 | 22.2% |
| 1.5x | 6.0x | 1:4.0 | 20.0% |
| 2.0x | 6.0x | 1:3.0 | 25.0% |
| 2.0x | 7.0x | 1:3.5 | 22.2% |

**Formula**: Breakeven WR = 1 / (1 + R/R ratio)

### Profit Factor

**Formula**: PF = Total Wins / Total Losses

**Interpretation**:
- PF < 1.0: Losing strategy
- PF = 1.0: Break-even
- PF > 1.0: Profitable strategy
- PF > 1.5: Excellent strategy

---

## Support

**Issues with optimization?**
- Review [CLAUDE.md](../CLAUDE.md) for troubleshooting guide
- Check [user_config.py](../backend/scanner/config/user_config.py) for parameter validation
- Review backtest logs for errors

**Need help interpreting results?**
- See "Interpreting Results" section above
- Compare results with baseline (CURRENT config)
- Consider multiple metrics, not just one

**Want to test new parameters?**
- Add new config to `OPTIMIZATION_CONFIGS` array
- Follow existing config structure
- Run optimization script

---

**Last Updated**: November 6, 2025
**Script Location**: `backend/scripts/optimize_parameters_comprehensive.py`
**Results Location**: `backend/optimization_results.json`
