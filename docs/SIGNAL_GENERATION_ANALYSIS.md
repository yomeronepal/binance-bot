# Signal Generation Analysis

## Summary: Which Timeframe is Being Used?

### Answer: **5-minute (5m) timeframe**

---

## Complete Signal Generation Flow

### 1. Celery Beat Scheduler
**File**: `backend/config/celery.py`

```python
# Line 26-32
'scan-binance-market': {
    'task': 'scanner.tasks.celery_tasks.scan_binance_market',
    'schedule': 60.0,  # Every 60 seconds
    'options': {
        'expires': 50.0,  # Expire if not executed within 50 seconds
    }
}
```

**Frequency**: Runs every **60 seconds** (1 minute)

---

### 2. Market Scanner Task
**File**: `backend/scanner/tasks/celery_tasks.py`

```python
# Line 88-93
klines_data = await client.batch_get_klines(
    top_pairs,
    interval='5m',      # ← 5-MINUTE CANDLES
    limit=200,          # Fetches last 200 candles
    batch_size=20       # Processes 20 symbols at once
)
```

**Timeframe**: Fetches **5-minute candles**
**History**: Last **200 candles** = 16.7 hours of data

---

### 3. Signal Processing
**File**: `backend/scanner/tasks/celery_tasks.py`

```python
# Line 102
result = engine.process_symbol(symbol, '5m')  # ← PROCESSES ON 5m
```

**File**: `backend/scanner/strategies/signal_engine.py`

```python
# Line 343-346
def process_symbol(
    self,
    symbol: str,
    timeframe: str = '5m'  # ← DEFAULT IS 5m
):
```

**Timeframe**: Processes signals on **5-minute** data

---

### 4. Multi-Timeframe Confirmation (Phase 3)
**File**: `backend/scanner/strategies/signal_engine.py`

```python
# Line 278-336
def _get_higher_timeframe_trend(self, symbol: str) -> str:
    """Get daily trend direction using multi-factor analysis"""
    # Fetches DAILY (1d) candles for trend confirmation
    # Returns: BULLISH, BEARISH, or NEUTRAL
```

**Purpose**: While signals are generated on **5m**, they are **filtered** using **daily (1d)** trend
**Logic**:
- Entry signal from **5m** data
- Trend confirmation from **1d** data
- Only takes trades aligned with daily trend

---

## Complete Timeframe Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CELERY BEAT (Every 60 seconds)                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SCAN BINANCE MARKET TASK                                   │
│  • Fetch top ~436 USDT pairs                                │
│  • Get last 200 candles @ 5m interval                       │
│  • Total data: 16.7 hours per symbol                        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SIGNAL DETECTION ENGINE (5m timeframe)                     │
│  • Calculate indicators on 5m data                          │
│  • Check RSI, ADX, EMA, MACD, etc.                          │
│  • Detect LONG/SHORT entry conditions                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3 FILTERS (on 5m signals)                            │
│  1. ADX Filter: Skip if ADX < 18 (ranging market)           │
│  2. Volume Spike: Skip if volume < 1.2x average             │
│  3. MTF Confirmation: Fetch DAILY trend                     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  DAILY TREND CONFIRMATION (1d timeframe)                    │
│  • Fetch last 50 daily candles                              │
│  • Calculate: EMA20 slope, MACD, Price vs EMA50             │
│  • Determine: BULLISH / BEARISH / NEUTRAL                   │
│  • Filter: Skip LONG if daily is BEARISH                    │
│           Skip SHORT if daily is BULLISH                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SIGNAL CREATED & SAVED                                     │
│  • Entry price from current 5m candle                       │
│  • SL/TP calculated using ATR from 5m data                  │
│  • Signal stored in database                                │
│  • Broadcast to frontend via WebSocket                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Why 5-Minute Timeframe?

### Historical Context
From the codebase comments and previous optimization:

1. **Original Design**: Started with 5m as a scalping strategy
2. **Phase 1 Testing**: Tested multiple timeframes (5m, 15m, 1h, 4h)
3. **Results**:
   - 5m: 8.6% win rate (too noisy)
   - 15m: 10% win rate
   - 1h: 15% win rate
   - **4h: 22.2% win rate** ← BEST for backtesting

**Status**: Live scanner still uses **5m**, but backtests use **4h**

---

## Discrepancy: Live vs Backtest Timeframes

### Live Trading (Current)
```python
# celery_tasks.py line 88-102
interval='5m'  # Live scanner uses 5-minute
process_symbol(symbol, '5m')
```

### Backtesting (Optimal)
```python
# parameter_sweep_breathing_room.py line 75
"timeframe": "4h"  # Backtests use 4-hour
```

### Why the Difference?

**Live Scanner (5m)**:
- ✅ Fast signal detection (new signals every 5 minutes)
- ✅ More frequent opportunities
- ❌ Noisy (8.6% win rate in testing)
- ❌ False signals from market noise

**Backtest (4h)**:
- ✅ Higher quality signals (22.2% win rate)
- ✅ Filters out noise
- ✅ Better risk/reward
- ❌ Slower (only 6 signals in 11 months)

---

## Recommendation: Align Live with Backtest

### Current Mismatch
- **Backtests**: Optimized on 4h → -0.03% ROI (almost profitable)
- **Live trading**: Running on 5m → Likely worse performance

### Proposed Fix
Change live scanner to use **4h timeframe** to match backtest optimization:

```python
# backend/scanner/tasks/celery_tasks.py

# OLD (line 88-90)
klines_data = await client.batch_get_klines(
    top_pairs,
    interval='5m',      # ← CHANGE THIS
    limit=200,
    batch_size=20
)

# NEW (recommended)
klines_data = await client.batch_get_klines(
    top_pairs,
    interval='4h',      # ← Use 4h like backtests
    limit=200,          # 200 * 4h = 800 hours = 33 days
    batch_size=20
)

# And update (line 102)
result = engine.process_symbol(symbol, '4h')  # ← Use 4h
```

### Impact of Change
- **Pros**:
  - Matches backtest optimization (OPT6 config)
  - Should achieve ~22% win rate (vs current 8.6%)
  - Less noise, higher quality signals
  - Parameters already optimized for 4h

- **Cons**:
  - Fewer signals (6 per year per symbol vs ~100s)
  - Slower to detect opportunities
  - Need to wait 4 hours for new candle

### Frequency Adjustment
If using 4h timeframe, also adjust scan frequency:

```python
# backend/config/celery.py

# OLD
'scan-binance-market': {
    'schedule': 60.0,  # Every 60 seconds (wasteful for 4h)
}

# NEW (recommended for 4h)
'scan-binance-market': {
    'schedule': 14400.0,  # Every 4 hours (when new candle closes)
    # Or: 'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
}
```

---

## Alternative: Multi-Timeframe Hybrid

Keep 5m for detection, but add stricter filters:

```python
# Option: Scan 5m but only trade on 4h alignment

async def _scan_market_async(engine):
    # Fetch 5m candles
    klines_5m = await client.batch_get_klines(top_pairs, interval='5m', limit=200)

    # Also fetch 4h candles
    klines_4h = await client.batch_get_klines(top_pairs, interval='4h', limit=200)

    for symbol in top_pairs:
        # Detect on 5m (fast)
        signal_5m = engine.process_symbol(symbol, '5m')

        if signal_5m:
            # Confirm on 4h (quality)
            signal_4h = engine.process_symbol(symbol, '4h')

            # Only trade if BOTH agree
            if signal_4h and signal_5m['direction'] == signal_4h['direction']:
                # High confidence signal!
                save_signal(signal_5m)
```

**Benefits**:
- Fast detection (5m)
- Quality confirmation (4h)
- Best of both worlds

---

## Current Issue: Why Live Trading May Not Match Backtests

### The Problem
1. **Backtests optimized on 4h** → Found OPT6 config with -0.03% ROI
2. **Live trading runs on 5m** → Using same OPT6 config
3. **Result**: Live performance likely worse than backtest

### Why OPT6 Won't Work on 5m
- **OPT6 parameters**: Optimized for 4h volatility
  - SL: 1.5 ATR (on 4h) = ~$450-600
  - SL: 1.5 ATR (on 5m) = ~$50-100 ← TOO TIGHT!
- **5m noise**: Gets stopped out by normal 5m candle wicks
- **4h stability**: Avoids noise, only real moves

---

## Breathing Room Hypothesis on 5m vs 4h

Your insight: "Stops are too tight, trades need room to breathe"

### On 4h Timeframe
- Current SL: 1.5 ATR = $450-600
- Normal volatility: $400-600
- **Problem**: SL barely outside noise (hitting stops)
- **Solution**: Breathing room sweep (2.0-3.5 ATR)

### On 5m Timeframe
- If using OPT6: 1.5 ATR = $50-100
- Normal 5m wick: $100-200
- **Problem**: SL INSIDE normal noise (guaranteed stop-outs!)
- **Solution**: Either use 4h OR massive SL (10+ ATR on 5m)

**Conclusion**: Your breathing room hypothesis is even MORE critical on 5m! But better to just use 4h like backtests.

---

## Summary Table

| Aspect | Live Trading (Current) | Backtesting (Optimal) | Recommendation |
|--------|----------------------|----------------------|----------------|
| **Timeframe** | 5m | 4h | Use 4h for live |
| **Scan Frequency** | Every 60 seconds | N/A | Every 4 hours |
| **Candles Fetched** | 200 (16.7 hours) | Full 11 months | 200 (33 days) |
| **Win Rate (tested)** | 8.6% | 22.2% | Use 4h config |
| **SL (OPT6)** | 1.5 ATR ≈ $50-100 | 1.5 ATR ≈ $450-600 | Need wider on 4h |
| **Signals/Year** | ~100s per symbol | ~6 per symbol | Quality over quantity |
| **MTF Confirmation** | Yes (1d) | Yes (1d) | Keep |
| **Issue** | Too noisy, stops too tight | Almost profitable | Align with backtest |

---

## Action Items

### Immediate (To Match Backtest)
1. ✅ Change `interval='5m'` to `interval='4h'` in celery_tasks.py line 88
2. ✅ Change `process_symbol(symbol, '5m')` to `'4h'` in line 102
3. ✅ Adjust scan frequency from 60s to 14400s (4h) in celery.py
4. ✅ Test with one symbol to verify signals match backtest

### After VPN Setup
1. ✅ Run breathing room parameter sweep (already queued)
2. ✅ Find optimal SL/TP for 4h timeframe
3. ✅ Update live scanner with winning config
4. ✅ Deploy to paper trading for validation

### Future Optimization
1. Consider multi-timeframe hybrid (5m detection + 4h confirmation)
2. Test if breathing room configs work better on 5m
3. Separate configs: 5m for scalping, 4h for swing trading

---

## Files to Modify (For 4h Alignment)

### 1. Scanner Task
**File**: `backend/scanner/tasks/celery_tasks.py`

**Line 88**: `interval='5m'` → `interval='4h'`
**Line 102**: `process_symbol(symbol, '5m')` → `process_symbol(symbol, '4h')`

### 2. Celery Schedule
**File**: `backend/config/celery.py`

**Line 28**: `'schedule': 60.0` → `'schedule': 14400.0`

### 3. Futures Scanner (if used)
**File**: `backend/scanner/tasks/celery_tasks.py` (futures section)

**Line ~650**: Same changes for futures market

---

## Conclusion

**Your signals are currently being generated on 5-minute timeframe**, but:
- ❌ Backtests were optimized on **4-hour** timeframe
- ❌ OPT6 config won't work properly on 5m (stops too tight)
- ❌ 5m has 8.6% win rate vs 4h's 22.2% win rate
- ✅ **Solution**: Align live trading with backtest (use 4h)
- ✅ **Your breathing room insight** is correct and even more critical on 5m!

**Next Steps**:
1. Start Docker Desktop
2. Run containers with VPN
3. Change scanner to 4h timeframe
4. Resume breathing room parameter sweep
5. Find optimal config for 4h
6. Deploy and profit! 🎯
