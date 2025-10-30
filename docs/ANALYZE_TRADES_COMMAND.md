# Analyze Trades Management Command

## Overview

The `analyze_trades` Django management command provides comprehensive analysis of paper trades with diagnostics and actionable recommendations for trading parameter optimization.

## Location

File: `backend/signals/management/commands/analyze_trades.py`

## Features

1. **Trade Statistics** - Count of open/closed/cancelled trades
2. **Sample Trades Table** - Visual table showing TP/SL distances and Risk/Reward ratios
3. **TP/SL Distance Analysis** - Average distances for LONG and SHORT trades
4. **Parameter Diagnosis** - Automated detection of problematic TP/SL settings
5. **Closed Trades Performance** - Win rate, profit factor, P&L metrics
6. **Current Parameters Display** - Shows active SignalConfig values
7. **Actionable Recommendations** - Step-by-step guidance based on trade status

---

## Usage

### Basic Usage

```bash
# Inside Docker container
docker-compose exec backend python manage.py analyze_trades

# Or directly if in backend directory with venv
cd backend
python manage.py analyze_trades
```

### Command Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--status` | string | `OPEN` | Trade status to analyze: `OPEN`, `CLOSED`, `CANCELLED`, or `ALL` |
| `--limit` | integer | `10` | Number of sample trades to display |
| `--days` | integer | None | Analyze trades from last N days |
| `--symbol` | string | None | Filter by specific trading symbol |

### Examples

```bash
# Analyze all open trades (default)
docker-compose exec backend python manage.py analyze_trades

# Analyze closed trades to check performance
docker-compose exec backend python manage.py analyze_trades --status CLOSED

# Show 20 sample trades instead of default 10
docker-compose exec backend python manage.py analyze_trades --limit 20

# Analyze trades from last 7 days
docker-compose exec backend python manage.py analyze_trades --days 7

# Analyze specific symbol
docker-compose exec backend python manage.py analyze_trades --symbol BTCUSDT

# Combine filters: BTCUSDT closed trades from last 30 days
docker-compose exec backend python manage.py analyze_trades \
  --status CLOSED \
  --symbol BTCUSDT \
  --days 30

# Analyze all trade statuses
docker-compose exec backend python manage.py analyze_trades --status ALL
```

---

## Output Sections

### 1. Overall Statistics

Displays total trade counts by status:
- Total trades analyzed
- Open count
- Closed count
- Cancelled count
- Time period filter (if used)
- Symbol filter (if used)

### 2. Sample Trades Table

Shows detailed table with columns:
- **Symbol** - Trading pair (e.g., BTCUSDT)
- **Dir** - Direction (LONG/SHORT)
- **Entry** - Entry price ($)
- **TP** - Take profit price ($)
- **SL** - Stop loss price ($)
- **TP%** - Take profit distance as percentage
- **SL%** - Stop loss distance as percentage
- **R/R** - Risk/Reward ratio

Example:
```
Symbol       Dir    Entry           TP           SL      TP%      SL%    R/R
--------------------------------------------------------------------------------
BTCUSDT      LONG    $43250.00  $45100.00  $42000.00    4.28%    2.89%  1.48
ETHUSDT      SHORT   $2250.00   $2150.00   $2320.00     4.44%    3.11%  1.43
```

### 3. TP/SL Distance Analysis

Calculates average TP and SL distances for LONG and SHORT trades separately:
- Average TP distance (%)
- Average SL distance (%)
- Risk/Reward Ratio

**Diagnosis provided:**
- ✅ Green: Reasonable targets (TP <3%, SL <2.5%)
- ⚠️  Yellow: Somewhat far targets (TP 3-5%, SL 2.5-4%)
- ❌ Red: TOO FAR targets (TP >5%, SL >4%)

### 4. Closed Trades Performance

Only shown when analyzing CLOSED or ALL trades:
- **Win Rate** - Percentage of winning vs losing trades
- **Total P&L** - Total profit/loss across all closed trades
- **Average P&L** - Average profit/loss per trade
- **Average Win** - Average winning trade amount
- **Average Loss** - Average losing trade amount
- **Profit Factor** - Total wins / Total losses ratio

**Performance Assessment:**
- Win Rate: Excellent (≥60%), Good (50-59%), Average (40-49%), Poor (<40%)
- Profit Factor: Excellent (≥2.0), Good (1.5-1.99), Breakeven (1.0-1.49), Losing (<1.0)

### 5. Current Signal Engine Parameters

Displays active trading parameters from `SignalConfig`:
- LONG RSI Range
- SHORT RSI Range
- ADX Minimum (LONG)
- ADX Minimum (SHORT)
- SL ATR Multiplier
- TP ATR Multiplier
- Min Confidence
- Volume Multiplier

### 6. Recommended Actions

Context-aware recommendations based on trade status:

**For OPEN trades:**
1. Adjust TP/SL in SignalConfig if needed
2. Restart services to apply changes
3. Wait for trades to close and re-analyze

**For CLOSED trades:**
- If ≥50 trades: Ready for ML optimization, Walk-Forward, Monte Carlo
- If <50 trades: Keep trading to gather more data

**Always includes:**
4. Monitor Learning System - Check trade counters
5. Trigger Manual Optimization - API command example

---

## Interpretation Guide

### TP/SL Distance Problems

**Problem: TP targets TOO FAR (>5%)**
- **Symptom**: No trades hitting TP
- **Cause**: Unrealistic profit targets
- **Fix**: Reduce `tp_atr_multiplier` to 1.5-2.5 in `signal_engine.py`

**Problem: SL targets TOO FAR (>4%)**
- **Symptom**: Large losses when SL hit
- **Cause**: Giving market too much room
- **Fix**: Reduce `sl_atr_multiplier` to 1.0-1.5 in `signal_engine.py`

### Win Rate Interpretation

- **≥60%**: Excellent - Strategy performing very well
- **50-59%**: Good - Profitable with good profit factor
- **40-49%**: Average - Needs higher profit factor to compensate
- **<40%**: Poor - Strategy needs optimization

### Profit Factor Interpretation

- **≥2.0**: Excellent - Wins are 2x+ larger than losses
- **1.5-1.99**: Good - Healthy profitability
- **1.0-1.49**: Breakeven - Breaking even or slight profit
- **<1.0**: Losing - Losses exceed wins

---

## Integration with Optimization System

This command helps you:

1. **Diagnose Issues** - Identify if TP/SL settings are problematic
2. **Track Progress** - Monitor win rate and profit factor over time
3. **Decide When to Optimize** - Know when you have enough data (≥50 closed trades)
4. **Validate Changes** - Compare before/after when adjusting parameters

**Workflow:**
```bash
# Step 1: Analyze current open trades
python manage.py analyze_trades --status OPEN

# Step 2: If TP/SL too far, edit signal_engine.py and restart services

# Step 3: Wait for trades to close (50-100 trades)

# Step 4: Analyze closed trades performance
python manage.py analyze_trades --status CLOSED

# Step 5: If ≥50 closed trades, trigger ML optimization
curl -X POST http://localhost:8000/api/learning/optimize/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{"volatility_level": "HIGH", "lookback_days": 30}'
```

---

## Related Commands and APIs

### Check Trade Counters (via Django shell)
```bash
docker-compose exec backend python manage.py shell -c "
from signals.models_optimization import TradeCounter
for c in TradeCounter.objects.all():
    print(f'{c.volatility_level}: {c.trade_count}/{c.threshold}')
"
```

### Trigger Manual Optimization (via API)
```bash
curl -X POST http://localhost:8000/api/learning/optimize/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "volatility_level": "HIGH",
    "lookback_days": 30
  }'
```

### View Optimization History (via API)
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/history/?volatility=HIGH&time_range=30d"
```

---

## Troubleshooting

### Command Not Found

**Error:** `Unknown command: 'analyze_trades'`

**Solution:**
1. Ensure file exists: `backend/signals/management/commands/analyze_trades.py`
2. Ensure directories have `__init__.py` files:
   - `backend/signals/management/__init__.py`
   - `backend/signals/management/commands/__init__.py`
3. Restart Django: `docker-compose restart backend`

### No Trades Found

**Error:** `No trades found with status=OPEN`

**Solution:**
- Check if paper trading is active
- Verify trades exist: `docker-compose exec backend python manage.py shell -c "from signals.models import PaperTrade; print(PaperTrade.objects.count())"`
- Try different status: `--status ALL`

### ImportError: SignalConfig

**Error:** `Could not import SignalConfig`

**Solution:**
- Verify file exists: `backend/scanner/strategies/signal_engine.py`
- Check SignalConfig class is defined
- Restart backend: `docker-compose restart backend`

---

## File Location Reference

| File | Purpose |
|------|---------|
| `backend/signals/management/commands/analyze_trades.py` | Management command source |
| `backend/scanner/strategies/signal_engine.py` | Trading strategy parameters to adjust |
| `docs/OPTIMIZATION_API_REFERENCE.md` | API endpoints for optimization system |
| `docs/PHASE6_AUTO_OPTIMIZATION_COMPLETE.md` | Complete Phase 6 documentation |

---

## Example Output

```
================================================================================
                          PAPER TRADE ANALYSIS
================================================================================

📊 OVERALL STATISTICS
  Total trades analyzed: 156
  • Open: 142
  • Closed: 12
  • Cancelled: 2

📋 SAMPLE TRADES (showing 10 of 156)
Symbol       Dir    Entry           TP           SL      TP%      SL%    R/R
--------------------------------------------------------------------------------
BTCUSDT      LONG    $43250.00  $45100.00  $42000.00    4.28%    2.89%  1.48
ETHUSDT      LONG    $2250.00   $2348.00   $2180.00     4.36%    3.11%  1.40
BNBUSDT      SHORT   $315.50    $305.20    $322.80      3.27%    2.31%  1.41

📏 TP/SL DISTANCE ANALYSIS

LONG Trades (95 total):
  Average TP distance: 5.80%
  Average SL distance: 4.20%
  Risk/Reward Ratio: 1:1.38

  🔍 DIAGNOSIS for LONG:
    ⚠️  PROBLEM: TP targets are TOO FAR (5.8%)
       No trades hitting TP because targets are unrealistic
       Recommendation: Reduce tp_atr_multiplier to 1.5-2.5
    ⚠️  PROBLEM: SL targets are TOO FAR (4.2%)
       Giving market too much room, risking large losses
       Recommendation: Reduce sl_atr_multiplier to 1.0-1.5

SHORT Trades (61 total):
  Average TP distance: 5.50%
  Average SL distance: 4.10%
  Risk/Reward Ratio: 1:1.34

  🔍 DIAGNOSIS for SHORT:
    ⚠️  TP targets are somewhat far (5.5%)
       Consider reducing slightly for faster wins
    ⚠️  SL targets are somewhat wide (4.1%)
       Consider tightening for better risk management

💰 CLOSED TRADES PERFORMANCE (12 trades)
  Win Rate: 58.3% (7W / 5L)
  Total P&L: $285.50
  Average P&L per trade: $23.79
  Average Win: $62.30
  Average Loss: -$34.20
  Profit Factor: 1.82

  📈 PERFORMANCE ASSESSMENT:
    ✅ Good win rate (58.3%)
    ✅ Good profit factor (1.82)

⚙️  CURRENT SIGNAL ENGINE PARAMETERS

  📋 Default Configuration:
     LONG RSI Range: 30 - 40
     SHORT RSI Range: 60 - 70
     ADX Minimum (LONG): 20
     ADX Minimum (SHORT): 20
     SL ATR Multiplier: 3.0x
     TP ATR Multiplier: 4.5x
     Min Confidence: 70%
     Volume Multiplier: 1.5x

================================================================================
                          RECOMMENDED ACTIONS
================================================================================

⚠️  You have 142 open trades - TP/SL might need adjustment

1️⃣  IMMEDIATE FIX - Adjust TP/SL in SignalConfig:
   • Edit: backend/scanner/strategies/signal_engine.py
   • Reduce tp_atr_multiplier to 1.5-2.5 (for faster wins)
   • Reduce sl_atr_multiplier to 1.0-1.5 (tighter risk control)
   • This allows trades to close and generate performance data

2️⃣  RESTART SERVICES:
   docker-compose restart backend celery-worker

3️⃣  WAIT FOR TRADES TO CLOSE:
   • Let 50-100 trades close with new parameters
   • Then run: python manage.py analyze_trades --status CLOSED

4️⃣  MONITOR LEARNING SYSTEM:
   • Check trade counters: python manage.py shell -c "
     from signals.models_optimization import TradeCounter;
     for c in TradeCounter.objects.all(): print(f'{c.volatility_level}: {c.trade_count}/{c.threshold}')"

5️⃣  TRIGGER MANUAL OPTIMIZATION:
   • curl -X POST http://localhost:8000/api/learning/optimize/ \
       -H 'Authorization: Bearer TOKEN' \
       -d '{"volatility_level": "HIGH", "lookback_days": 30}'
```

---

## Summary

The `analyze_trades` command is your primary diagnostic tool for:
- Understanding current trading performance
- Identifying parameter issues
- Deciding when to run optimization
- Validating strategy changes

Use it regularly to monitor your trading bot's health and make data-driven decisions about parameter adjustments.
