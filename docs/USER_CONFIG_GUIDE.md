# User Configuration Guide

Quick guide for updating trading parameters manually.

## 📁 Configuration File Location

**File**: `backend/scanner/config/user_config.py`

This is your **one-stop shop** for all trading parameters. Simply edit this file and restart services to apply changes.

---

## 🚀 Quick Start

### 1. Open Configuration File

```bash
# Windows
notepad backend\scanner\config\user_config.py

# Linux/Mac
nano backend/scanner/config/user_config.py
```

### 2. Edit Parameters

Find the section you want to modify (Binance or Forex) and change values:

```python
# Example: Make Binance more aggressive
BINANCE_CONFIG = {
    "long_rsi_min": 20.0,        # Changed from 23.0 (more aggressive)
    "long_rsi_max": 30.0,        # Changed from 33.0 (tighter range)
    "long_adx_min": 25.0,        # Changed from 22.0 (stronger trends)
    "min_confidence": 0.75,      # Changed from 0.73 (higher quality)
    # ... rest of config
}
```

### 3. Validate Changes

```bash
# Test your changes before applying
python backend/scanner/config/user_config.py
```

**Expected Output**:
```
================================================================================
USER CONFIGURATION VALIDATION
================================================================================

BINANCE Configuration:
  ✅ VALID

FOREX Configuration:
  ✅ VALID

================================================================================
✅ ALL CONFIGURATIONS VALID
================================================================================
```

### 4. Restart Services

```bash
# Docker Compose
docker-compose restart backend celery_worker celery_beat

# Or using shortcuts
make docker-restart          # Linux/Mac
run.bat docker-restart       # Windows
```

### 5. Verify Applied

```bash
# Check logs for confirmation
docker logs binancebot_backend | grep "Loaded.*config from user_config"

# Should see:
# ✅ Loaded Binance config from user_config.py
# ✅ Loaded Forex config from user_config.py
```

---

## 📊 Key Parameters Explained

### RSI (Relative Strength Index)

Controls when to enter trades based on overbought/oversold conditions.

```python
"long_rsi_min": 23.0,   # LONG entry starts when RSI drops to this level
"long_rsi_max": 33.0,   # LONG entry stops when RSI rises above this level
```

**Effect**:
- **Lower range (20-30)**: More aggressive, more signals, lower quality
- **Higher range (25-35)**: Less aggressive, fewer signals, higher quality
- **Tighter range (23-33)**: Very selective, fewest signals, highest quality ✅ Current

**Example Adjustments**:
```python
# More signals (aggressive)
"long_rsi_min": 20.0,
"long_rsi_max": 35.0,

# Fewer signals (conservative)
"long_rsi_min": 25.0,
"long_rsi_max": 30.0,
```

### ADX (Trend Strength)

Controls minimum trend strength required for trading.

```python
"long_adx_min": 22.0,   # Minimum ADX value to enter trade
```

**Effect**:
- **Lower (18-20)**: Weaker trends OK, more signals, more false signals
- **Medium (22-25)**: Moderate trends required, balanced ✅ Current
- **Higher (25-30)**: Strong trends only, fewer signals, higher quality

**Guidelines**:
- Forex: 18-22 (trends are smoother)
- Crypto 4H: 22-25 (balanced)
- Crypto 1D: 28-32 (very strong trends)

### SL/TP (Stop Loss / Take Profit)

Controls risk management via ATR multiples.

```python
"sl_atr_multiplier": 1.5,   # Stop Loss = Entry ± (1.5 × ATR)
"tp_atr_multiplier": 5.25,  # Take Profit = Entry ± (5.25 × ATR)
```

**Risk/Reward Ratio**: TP ÷ SL = 5.25 ÷ 1.5 = **3.5** (1:3.5)

**Effect**:
- **Tighter SL (1.0-1.5)**: Less breathing room, more stop-outs, lower loss per trade
- **Wider SL (2.0-3.0)**: More breathing room, fewer stop-outs, higher loss per trade
- **Higher TP (6.0-8.0)**: Larger targets, harder to hit, better R/R ratio
- **Lower TP (4.0-5.0)**: Smaller targets, easier to hit, lower R/R ratio

**Breakeven Win Rate**:
| R/R Ratio | Required Win Rate |
|-----------|-------------------|
| 1:2.0 | 33.3% |
| 1:2.5 | 28.6% |
| 1:3.0 | 25.0% |
| 1:3.5 | 22.2% ✅ Current |
| 1:4.0 | 20.0% |

**Example Adjustments**:
```python
# More conservative (easier to profit)
"sl_atr_multiplier": 2.0,
"tp_atr_multiplier": 6.0,   # 1:3.0 R/R, need 25% win rate

# More aggressive (harder to profit, but bigger wins)
"sl_atr_multiplier": 1.2,
"tp_atr_multiplier": 5.0,   # 1:4.2 R/R, need 19.2% win rate
```

### Confidence Threshold

Minimum quality score required to generate signal.

```python
"min_confidence": 0.73,   # 73% confidence minimum
```

**Effect**:
- **Lower (0.65-0.70)**: Many signals, lower average quality
- **Medium (0.70-0.75)**: Balanced ✅ Current
- **Higher (0.75-0.85)**: Few signals, very high quality

**Example Adjustments**:
```python
# More signals
"min_confidence": 0.68,

# Fewer but better signals
"min_confidence": 0.78,
```

---

## 🎯 Common Adjustments

### Increase Number of Signals

```python
BINANCE_CONFIG = {
    "long_rsi_min": 20.0,        # Wider range
    "long_rsi_max": 35.0,        # Wider range
    "long_adx_min": 20.0,        # Lower ADX
    "min_confidence": 0.68,      # Lower confidence
    # ...
}
```

**Trade-off**: More signals but lower average quality

### Improve Win Rate

```python
BINANCE_CONFIG = {
    "long_rsi_min": 23.0,        # Keep tight range
    "long_rsi_max": 30.0,        # Tighter range
    "long_adx_min": 25.0,        # Higher ADX (stronger trends)
    "min_confidence": 0.76,      # Higher confidence
    "sl_atr_multiplier": 2.0,    # More breathing room
    # ...
}
```

**Trade-off**: Fewer signals but higher win rate

### Better Risk/Reward

```python
BINANCE_CONFIG = {
    "sl_atr_multiplier": 1.5,    # Keep tight stop
    "tp_atr_multiplier": 6.0,    # Wider target (1:4 R/R)
    # ...
}
```

**Trade-off**: Better R/R but harder to hit targets

---

## ⚙️ Timeframe-Specific Overrides

To use **different parameters per timeframe**, edit `TIMEFRAME_OVERRIDES`:

```python
TIMEFRAME_OVERRIDES = {
    "15m": {
        "binance": {
            "long_adx_min": 25.0,        # Stronger trend for 15m
            "min_confidence": 0.75,       # Higher quality for short TF
        }
    },

    "4h": {
        "binance": {},  # Empty = use BINANCE_CONFIG defaults
    },

    "1d": {
        "binance": {
            "long_adx_min": 30.0,        # Very strong trend for daily
            "sl_atr_multiplier": 3.0,     # Wide stop for swing trades
            "tp_atr_multiplier": 8.0,     # Large target
        }
    }
}
```

**When to use**:
- Short timeframes (15m, 1h): Higher ADX, tighter stops
- Long timeframes (1d): Lower ADX, wider stops/targets

---

## 📋 Validation Checklist

Before restarting services, ensure:

- [ ] RSI ranges are valid (long_min < long_max)
- [ ] ADX values are reasonable (15-35)
- [ ] TP > SL (positive risk/reward ratio)
- [ ] Confidence is between 0.5-1.0
- [ ] Run validation script: `python backend/scanner/config/user_config.py`
- [ ] Check for ✅ VALID messages

---

## 🛠️ Advanced: Per-Market Differences

### Binance (Crypto) Characteristics

```python
BINANCE_CONFIG = {
    "long_adx_min": 22.0,        # Higher (stronger trends)
    "sl_atr_multiplier": 1.5,    # Tighter (crypto volatile)
    "tp_atr_multiplier": 5.25,   # 1:3.5 R/R
    "min_confidence": 0.73,      # Higher (stricter filter)
}
```

**Why**: Crypto is more volatile, needs tighter stops and stricter quality

### Forex Characteristics

```python
FOREX_CONFIG = {
    "long_adx_min": 20.0,        # Lower (smoother trends)
    "sl_atr_multiplier": 2.0,    # Wider (needs breathing room)
    "tp_atr_multiplier": 6.0,    # 1:3.0 R/R
    "min_confidence": 0.70,      # Lower (more signals)
}
```

**Why**: Forex is less volatile, smoother trends, needs more breathing room

---

## 🚨 Common Mistakes

### ❌ Don't Do This

```python
# BAD: TP less than SL (negative R/R)
"sl_atr_multiplier": 3.0,
"tp_atr_multiplier": 2.0,  # ❌ Can't be profitable!

# BAD: Impossible RSI range
"long_rsi_min": 35.0,
"long_rsi_max": 25.0,      # ❌ Min > Max!

# BAD: ADX too high
"long_adx_min": 50.0,      # ❌ Almost no signals!

# BAD: Confidence too high
"min_confidence": 0.95,    # ❌ Almost no signals!
```

### ✅ Do This Instead

```python
# GOOD: Proper ranges and ratios
"sl_atr_multiplier": 1.5,
"tp_atr_multiplier": 5.25,  # ✅ 1:3.5 R/R

"long_rsi_min": 23.0,
"long_rsi_max": 33.0,       # ✅ Proper range

"long_adx_min": 22.0,       # ✅ Reasonable

"min_confidence": 0.73,     # ✅ Balanced
```

---

## 📈 Testing Your Changes

### 1. Backtest Before Live

```bash
# Run backtest with new parameters
curl -X POST http://localhost:8000/api/backtest/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test New Parameters",
    "symbols": ["BTCUSDT"],
    "timeframe": "4h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-11-01T00:00:00Z",
    "initial_capital": 10000
  }'
```

### 2. Monitor First Signals

```bash
# Watch for new signals
docker logs -f binancebot_celery_worker | grep "New.*signal"
```

### 3. Compare Performance

Track these metrics over 1-2 weeks:
- Number of signals generated
- Win rate
- Average P&L per trade
- Max drawdown

---

## 🔄 Quick Parameter Templates

### Template 1: Aggressive (More Signals)

```python
"long_rsi_min": 20.0,
"long_rsi_max": 35.0,
"long_adx_min": 20.0,
"min_confidence": 0.68,
"sl_atr_multiplier": 1.5,
"tp_atr_multiplier": 5.0,
```

### Template 2: Conservative (Quality)

```python
"long_rsi_min": 23.0,
"long_rsi_max": 30.0,
"long_adx_min": 25.0,
"min_confidence": 0.76,
"sl_atr_multiplier": 2.0,
"tp_atr_multiplier": 6.0,
```

### Template 3: Balanced (Current OPT6)

```python
"long_rsi_min": 23.0,
"long_rsi_max": 33.0,
"long_adx_min": 22.0,
"min_confidence": 0.73,
"sl_atr_multiplier": 1.5,
"tp_atr_multiplier": 5.25,
```

---

## 📞 Support

**Validation Failed?**
- Check error messages from validation script
- Ensure all ranges are logical (min < max)
- Verify TP > SL for positive R/R

**Changes Not Applied?**
- Confirm services restarted: `docker-compose ps`
- Check logs: `docker logs binancebot_backend`
- Look for "Loaded config from user_config.py" message

**Need Help?**
- Review parameter guidelines in `user_config.py` (comments)
- Run validation: `python manage.py validate_configs --verbose`
- Check documentation: `backend/scanner/config/README.md`

---

**Last Updated**: November 6, 2025
**Config File**: `backend/scanner/config/user_config.py`
