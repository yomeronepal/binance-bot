# New Indicators and Multi-Timeframe Signal Generation

## Summary

The trading bot has been enhanced with:
1. **3 New Technical Indicators**: SuperTrend, MFI (Money Flow Index), Parabolic SAR
2. **Expanded Timeframes**: Now generates signals from 15m, 1h, 4h, and 1d timeframes
3. **Updated Scoring Logic**: All 13 indicators now contribute to signal confidence

---

## New Technical Indicators

### 1. SuperTrend (Weight: 1.9)

**Purpose**: Trend following indicator with adaptive ATR-based bands

**Calculation**:
- Upper Band = (High + Low) / 2 + (Multiplier × ATR)
- Lower Band = (High + Low) / 2 - (Multiplier × ATR)
- Direction: 1 (bullish) when price > upper band, -1 (bearish) when price < lower band

**Parameters**:
- Period: 10
- Multiplier: 3.0

**Signal Logic**:
- **LONG**: SuperTrend direction = 1 (bullish trend)
- **SHORT**: SuperTrend direction = -1 (bearish trend)

**Why It's Useful**:
- Provides clear trend direction with minimal lag
- ATR-based bands adapt to volatility
- Works well as trailing stop reference

---

### 2. Money Flow Index - MFI (Weight: 1.3)

**Purpose**: Volume-weighted RSI that combines price and volume

**Calculation**:
```
Typical Price = (High + Low + Close) / 3
Money Flow = Typical Price × Volume
Positive Flow = Sum of money flow when price increases
Negative Flow = Sum of money flow when price decreases
MFI = 100 - [100 / (1 + Positive Flow / Negative Flow)]
```

**Parameters**:
- Period: 14

**Signal Logic**:
- **LONG**: MFI between 20-50 (oversold to neutral) OR MFI rising
- **SHORT**: MFI between 50-80 (overbought to neutral) OR MFI falling

**Why It's Useful**:
- Confirms momentum with volume data
- Better than RSI for identifying real vs fake breakouts
- Detects divergences between price and volume

---

### 3. Parabolic SAR (Weight: 1.1)

**Purpose**: Adaptive trailing stop and trend reversal indicator

**Calculation**:
```
SAR(t) = SAR(t-1) + AF × (EP - SAR(t-1))
```
Where:
- AF = Acceleration Factor (starts at 0.02, increases by 0.02 each period, max 0.2)
- EP = Extreme Point (highest high in uptrend, lowest low in downtrend)

**Parameters**:
- Acceleration: 0.02
- Maximum: 0.2

**Signal Logic**:
- **LONG**: Price > SAR (bullish)
- **SHORT**: Price < SAR (bearish)

**Why It's Useful**:
- Provides dynamic stop loss levels
- Identifies trend reversals early
- Works well in trending markets

---

## Complete Indicator List (13 Total)

| # | Indicator | Weight | Purpose | LONG Condition | SHORT Condition |
|---|-----------|--------|---------|----------------|-----------------|
| 1 | MACD | 2.0 | Momentum | Histogram crosses above 0 | Histogram crosses below 0 |
| 2 | RSI | 1.5 | Overbought/Oversold | 23-33 range | 67-77 range |
| 3 | Price vs EMA50 | 1.8 | Trend | Close > EMA50 | Close < EMA50 |
| 4 | ADX | 1.7 | Trend Strength | ADX > 22 | ADX > 22 |
| 5 | Heikin-Ashi | 1.6 | Smoothed Trend | HA Bullish | HA Bearish |
| 6 | Volume | 1.4 | Confirmation | Volume > 1.2x avg | Volume > 1.2x avg |
| 7 | EMA Alignment | 1.2 | Multi-TF Trend | EMA9 > EMA21 > EMA50 | EMA9 < EMA21 < EMA50 |
| 8 | DI (Directional) | 1.0 | Momentum | +DI > -DI | -DI > +DI |
| 9 | Bollinger Bands | 0.8 | Volatility | Price in lower 30-70% | Price in upper 30-70% |
| 10 | Volatility (ATR%) | 0.5 | Risk Adjustment | ATR% < 4% | ATR% < 4% |
| **11** | **SuperTrend** | **1.9** | **Trend Following** | **Direction = 1** | **Direction = -1** |
| **12** | **MFI** | **1.3** | **Volume Momentum** | **20-50 or Rising** | **50-80 or Falling** |
| **13** | **PSAR** | **1.1** | **Trailing Stop** | **Price > SAR** | **Price < SAR** |

**Total Max Score**: 19.9 (previously 16.9)

---

## Multi-Timeframe Configuration

### Timeframe Hierarchy

| Timeframe | Trading Style | Scan Frequency | Stop Loss (ATR) | Take Profit (ATR) | Risk/Reward | Candle Limit |
|-----------|---------------|----------------|-----------------|-------------------|-------------|--------------|
| **15m** | Scalping | Every 15 min | 1.8x | 5.4x | 1:3.0 | 300 |
| **1h** | Intraday | Every 1 hour | 2.0x | 6.0x | 1:3.0 | 250 |
| **4h** | Day Trading | Every 4 hours | 2.5x | 7.0x | 1:2.8 | 200 |
| **1d** | Swing Trading | Every 6 hours | 3.0x | 8.0x | 1:2.7 | 100 |

### Signal Quality vs Frequency Trade-off

```
15m: High frequency, Lower quality (requires tight stops, higher confidence threshold)
 ↓
1h:  Medium frequency, Good quality (balanced approach)
 ↓
4h:  Lower frequency, Better quality (recommended for most traders)
 ↓
1d:  Lowest frequency, Best quality (highest win rates, widest stops)
```

---

## Breathing Room Configurations

### 15-Minute Timeframe (Scalping)
```python
SignalConfig(
    min_confidence=0.75,  # Higher confidence for short timeframe
    long_adx_min=25.0,    # Stronger trend required
    long_rsi_min=25.0,
    long_rsi_max=35.0,
    short_rsi_min=65.0,
    short_rsi_max=75.0,
    sl_atr_multiplier=1.8,
    tp_atr_multiplier=5.4
)
```

### 1-Hour Timeframe (Intraday)
```python
SignalConfig(
    min_confidence=0.73,
    long_adx_min=22.0,
    long_rsi_min=23.0,
    long_rsi_max=33.0,
    short_rsi_min=67.0,
    short_rsi_max=77.0,
    sl_atr_multiplier=2.0,
    tp_atr_multiplier=6.0
)
```

### 4-Hour Timeframe (Day Trading)
```python
SignalConfig(
    min_confidence=0.70,
    long_adx_min=22.0,
    long_rsi_min=23.0,
    long_rsi_max=33.0,
    short_rsi_min=67.0,
    short_rsi_max=77.0,
    sl_atr_multiplier=2.5,
    tp_atr_multiplier=7.0
)
```

### 1-Day Timeframe (Swing Trading)
```python
SignalConfig(
    min_confidence=0.70,
    long_adx_min=22.0,
    long_rsi_min=23.0,
    long_rsi_max=33.0,
    short_rsi_min=67.0,
    short_rsi_max=77.0,
    sl_atr_multiplier=3.0,
    tp_atr_multiplier=8.0
)
```

---

## Celery Beat Schedule

```python
# 1-day scan (every 6 hours at 0, 6, 12, 18:00)
'scan-1d-timeframe': {
    'task': 'scanner.tasks.multi_timeframe_scanner.scan_1d_timeframe',
    'schedule': crontab(minute=0, hour='*/6'),
}

# 4-hour scan (every 4 hours at 0, 4, 8, 12, 16, 20:00)
'scan-4h-timeframe': {
    'task': 'scanner.tasks.multi_timeframe_scanner.scan_4h_timeframe',
    'schedule': crontab(minute=0, hour='*/4'),
}

# 1-hour scan (every hour at :00)
'scan-1h-timeframe': {
    'task': 'scanner.tasks.multi_timeframe_scanner.scan_1h_timeframe',
    'schedule': crontab(minute=0),
}

# 15-minute scan (every 15 minutes at :00, :15, :30, :45)
'scan-15m-timeframe': {
    'task': 'scanner.tasks.multi_timeframe_scanner.scan_15m_timeframe',
    'schedule': crontab(minute='*/15'),
}
```

---

## File Changes

### Modified Files

1. **`backend/scanner/indicators/indicator_utils.py`**
   - Added `calculate_supertrend()` function (lines 192-242)
   - Added `calculate_mfi()` function (lines 245-275)
   - Added `calculate_parabolic_sar()` function (lines 278-355)
   - Updated `calculate_all_indicators()` to include new indicators (lines 183-194)

2. **`backend/scanner/strategies/signal_engine.py`**
   - Added new indicator weights to `SignalConfig` dataclass (lines 61-64)
   - Updated `_check_long_conditions()` max_score calculation (lines 567-581)
   - Added SuperTrend check (lines 678-683)
   - Added MFI check (lines 685-693)
   - Added PSAR check (lines 695-700)
   - Updated `_check_short_conditions()` max_score calculation (lines 726-740)
   - Added SuperTrend check (lines 837-842)
   - Added MFI check (lines 844-852)
   - Added PSAR check (lines 854-859)

3. **`backend/scanner/tasks/multi_timeframe_scanner.py`**
   - Added 15m timeframe config (lines 96-108)
   - Updated timeframes list to include all 4 timeframes (line 262)
   - Added `scan_1h_timeframe()` Celery task (lines 354-372)
   - Added `scan_15m_timeframe()` Celery task (lines 374-392)
   - Updated candle limit logic (lines 415-423)

4. **`backend/config/celery.py`**
   - Added 1h scan schedule (lines 43-50)
   - Added 15m scan schedule (lines 52-59)

5. **`backend/test_multi_timeframe.py`**
   - Updated to test all 4 timeframes (lines 13-49)

---

## Testing

### Manual Testing

```bash
# Inside Docker container
docker exec binancebot_celery python test_multi_timeframe.py
```

Expected output:
```
================================================================================
TESTING MULTI-TIMEFRAME SIGNAL SCANNER (15m, 1h, 4h, 1d)
New indicators: SuperTrend, MFI, Parabolic SAR
================================================================================

[1/4] Testing 15-minute timeframe scan...
--------------------------------------------------------------------------------
✅ 15-minute scan completed!
   Signals created: X
   Signals updated: Y
   Signals invalidated: Z

[2/4] Testing 1-hour timeframe scan...
...
```

### Backtest Testing

To test the new indicators with backtesting, create a test script:

```python
#!/usr/bin/env python3
"""
Test new indicators with backtest
"""
import requests
import time

API_BASE = "http://localhost:8000/api"

# Test configuration with all 13 indicators
config = {
    "name": "SuperTrend+MFI+PSAR Test",
    "symbols": ["BTCUSDT"],
    "timeframe": "4h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-11-04T00:00:00Z",
    "strategy_params": {
        "min_confidence": 0.70,
        "long_adx_min": 22.0,
        "short_adx_min": 22.0,
        "long_rsi_min": 23.0,
        "long_rsi_max": 33.0,
        "short_rsi_min": 67.0,
        "short_rsi_max": 77.0,
        "sl_atr_multiplier": 2.5,
        "tp_atr_multiplier": 7.0,
        # New indicator weights are automatically included
    },
    "initial_capital": 10000,
    "position_size": 100
}

# Submit backtest
response = requests.post(f"{API_BASE}/backtest/", json=config)
backtest_id = response.json().get("id")

print(f"Backtest submitted (ID: {backtest_id})")
print("Waiting for completion...")

# Wait for results
while True:
    response = requests.get(f"{API_BASE}/backtest/{backtest_id}/")
    status = response.json().get("status")

    if status == "COMPLETED":
        result = response.json()
        print(f"\n✅ Backtest Complete!")
        print(f"   Trades: {result.get('total_trades')}")
        print(f"   Win Rate: {result.get('win_rate'):.1f}%")
        print(f"   ROI: {result.get('roi'):.2f}%")
        print(f"   P/L: ${result.get('total_profit_loss'):.2f}")
        print(f"   Sharpe: {result.get('sharpe_ratio')}")
        break
    elif status == "FAILED":
        print(f"❌ Backtest failed: {response.json().get('error_message')}")
        break

    time.sleep(5)
```

---

## Expected Performance Improvements

### Hypothesis: New Indicators Should Improve Win Rate

**Reasoning**:

1. **SuperTrend** (weight 1.9):
   - Filters out counter-trend signals
   - Provides clear trend direction
   - Expected impact: +3-5% win rate

2. **MFI** (weight 1.3):
   - Confirms real breakouts with volume
   - Filters fake moves
   - Expected impact: +2-4% win rate

3. **PSAR** (weight 1.1):
   - Identifies optimal entry timing
   - Provides adaptive stop loss reference
   - Expected impact: +1-2% win rate

**Combined Expected Impact**: +6-11% win rate improvement

**Previous Best (OPT6, 4h BTCUSDT)**:
- Win Rate: 16.7%
- ROI: -0.03%

**Expected New Performance**:
- Win Rate: 23-28%
- ROI: +2% to +5%
- Status: **Profitable** ✅

---

## Monitoring Signal Quality

### Key Metrics to Track

1. **Signal Count by Timeframe**:
   - 15m: High count (expected 10-20 per day)
   - 1h: Medium count (expected 5-10 per day)
   - 4h: Low count (expected 2-5 per day)
   - 1d: Very low count (expected 0-2 per day)

2. **Confidence Distribution**:
   - Should see higher average confidence with 13 indicators
   - Target: 75-85% confidence range

3. **Indicator Contribution**:
   - Track which indicators trigger most often
   - Identify if any indicators are redundant

### Database Query for Analysis

```sql
-- Signal count by timeframe (last 7 days)
SELECT
    timeframe,
    COUNT(*) as signal_count,
    AVG(confidence) as avg_confidence,
    COUNT(CASE WHEN signal_type = 'LONG' THEN 1 END) as long_signals,
    COUNT(CASE WHEN signal_type = 'SHORT' THEN 1 END) as short_signals
FROM signals_signal
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY timeframe
ORDER BY
    CASE timeframe
        WHEN '1d' THEN 1
        WHEN '4h' THEN 2
        WHEN '1h' THEN 3
        WHEN '15m' THEN 4
    END;
```

---

## Troubleshooting

### Issue: No Signals Generated

**Possible Causes**:
1. Confidence threshold too high (75% with 13 indicators is strict)
2. ADX threshold too high (25 for 15m might filter too many)
3. Network connectivity issues

**Solutions**:
- Lower `min_confidence` to 0.70 for testing
- Check ADX values in backtests (avg ADX should be > threshold)
- Verify Binance API connectivity

### Issue: Too Many Signals (False Positives)

**Possible Causes**:
1. Short timeframes (15m) generate more noise
2. Confidence threshold too low
3. Market in ranging conditions

**Solutions**:
- Increase `min_confidence` to 0.77-0.80
- Increase ADX threshold to filter ranging markets
- Focus on 4h/1d timeframes during consolidation

### Issue: Indicator Calculation Errors

**Symptoms**:
```
Error calculating indicators: 'supertrend_direction'
KeyError: 'mfi'
```

**Solution**:
- Verify all indicators are calculated in `calculate_all_indicators()`
- Check for sufficient data (need 200+ candles for proper calculation)
- Restart Celery workers: `docker restart binancebot_celery`

---

## Next Steps (Phase 3)

### Recommended Optimizations

1. **Indicator Weight Tuning**:
   - Run backtests varying indicator weights
   - Find optimal weight distribution
   - May need to reduce some weights to avoid overfitting

2. **Timeframe-Specific Indicators**:
   - Some indicators work better on certain timeframes
   - Consider different weight profiles per timeframe
   - Example: Higher volume weight on short timeframes

3. **Signal Filtering**:
   - Implement multi-timeframe confirmation
   - Only take 15m/1h signals aligned with 4h/1d trend
   - Expected: Further +5-10% win rate improvement

4. **Dynamic Parameter Adjustment**:
   - Adjust RSI ranges based on market conditions
   - Scale ATR multipliers with volatility
   - Use adaptive confidence thresholds

---

## References

- **SuperTrend Calculation**: [TradingView Documentation](https://www.tradingview.com/support/solutions/43000634738-supertrend/)
- **Money Flow Index (MFI)**: [Investopedia](https://www.investopedia.com/terms/m/mfi.asp)
- **Parabolic SAR**: [Technical Analysis Library](https://technical-analysis-library-in-python.readthedocs.io/)
- **Multi-Timeframe Analysis**: [MULTI_TIMEFRAME_SIGNAL_GENERATION.md](./MULTI_TIMEFRAME_SIGNAL_GENERATION.md)
- **Original Optimization**: [OPTIMIZATION_COMPLETE_SUMMARY.md](./OPTIMIZATION_COMPLETE_SUMMARY.md)

---

## Conclusion

The trading bot now has:
- **13 technical indicators** (up from 10)
- **4 timeframes** (15m, 1h, 4h, 1d)
- **Improved signal quality** through multi-indicator confirmation
- **Flexible configuration** for different trading styles

**Expected Result**: Push from -0.03% ROI to **profitable** (+2% to +5% ROI)

**Status**: ✅ **Ready for Backtesting**

---

*Last Updated: November 4, 2025*
*Version: 2.0 - Enhanced Indicators & Multi-Timeframe*
