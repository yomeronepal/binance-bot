# Multi-Timeframe Signal Generation with Breathing Room

## Summary

The trading bot has been upgraded to generate signals from **4-hour** and **1-day** timeframes instead of the previous 5-minute timeframe. This change is based on backtest results showing better performance with wider stop losses that give trades "breathing room".

## Key Changes

### 1. **Timeframe Optimization**
- **Old**: 5-minute timeframe (too noisy, low win rate)
- **New**: 4-hour and 1-day timeframes (better signal quality)

### 2. **Breathing Room Parameters**

Based on backtest results (see `backtest_data/high/dodge/breathing_room_results_1762245589.json`), we use wider stop losses:

| Timeframe | Stop Loss (ATR) | Take Profit (ATR) | Risk/Reward | Use Case |
|-----------|----------------|-------------------|-------------|----------|
| **1d** | 3.0x | 8.0x | 1:2.7 | Swing trading (6h scans) |
| **4h** | 2.5x | 7.0x | 1:2.8 | Day trading (4h scans) |
| **1h** | 2.0x | 6.0x | 1:3.0 | Active trading (optional) |

**Example Performance** (DOGEUSDT 1d, 2 years):
- Win Rate: 50%
- ROI: +0.88% to +0.98%
- Profit Factor: 3.79-4.43
- Sharp Ratio: 0.58-0.63

### 3. **Scan Schedule**

Celery Beat schedules:
- **1-day timeframe**: Every 6 hours (perfect for swing trading)
- **4-hour timeframe**: Every 4 hours (good balance)

## Implementation

### File Structure

```
backend/
├── scanner/tasks/
│   └── multi_timeframe_scanner.py    # NEW: Multi-timeframe scanner
├── config/
│   └── celery.py                     # UPDATED: Celery schedule
└── test_multi_timeframe.py            # TEST: Verification script
```

### Key Functions

**`multi_timeframe_scanner.py`**:
- `scan_1d_timeframe()` - Scan daily timeframe
- `scan_4h_timeframe()` - Scan 4-hour timeframe
- `scan_multi_timeframe()` - Scan both timeframes
- `_get_top_pairs_by_volume()` - Get top 200 pairs by 24h volume

### Configuration

**Breathing Room Configs** (`BREATHING_ROOM_CONFIGS`):
```python
'1d': SignalConfig(
    min_confidence=0.70,
    long_adx_min=22.0,
    long_rsi_min=23.0,
    long_rsi_max=33.0,
    short_rsi_min=67.0,
    short_rsi_max=77.0,
    sl_atr_multiplier=3.0,   # Wide stop for breathing room
    tp_atr_multiplier=8.0    # ~1:2.7 R/R
)
```

## Backtest Data

### Downloaded Dataset
- **Period**: 2 years (2023-2024)
- **Symbols**: 5 (BTCUSDT, ETHUSDT, ADAUSDT, SOLUSDT, DOGEUSDT)
- **Timeframes**: 5m, 15m, 1h, 4h, 1d
- **Total**: 25 CSV files, 200.43 MB
- **Location**: `backend/backtest_data/{volatility}/{SYMBOL}_{timeframe}.csv`

### Volatility Classification
- **Low**: BTCUSDT, ETHUSDT
- **Medium**: ADAUSDT, SOLUSDT
- **High**: DOGEUSDT

## Usage

### Manual Testing

```bash
# Inside Docker container
docker exec binancebot_celery python test_multi_timeframe.py
```

### Celery Tasks

```python
# Trigger manually
from scanner.tasks.multi_timeframe_scanner import scan_1d_timeframe, scan_4h_timeframe

# Run 1-day scan
result = scan_1d_timeframe()

# Run 4-hour scan
result = scan_4h_timeframe()
```

### Scheduled Execution

Tasks run automatically via Celery Beat:
- **1d scan**: Every 6 hours (0, 6, 12, 18:00)
- **4h scan**: Every 4 hours (0, 4, 8, 12, 16, 20:00)

## Key Improvements

### ✅ Completed
1. **Multi-timeframe Support**: Scan 4h and 1d timeframes
2. **Breathing Room**: Wider stop losses (2.5-3.0x ATR)
3. **Better Win Rates**: 50% win rate achieved on DOGEUSDT 1d
4. **Comprehensive Data**: 2 years of historical data for backtesting
5. **Fixed CSV Loading**: Compatible with 'timestamp' column
6. **Celery Queue Fix**: Backtest tasks now execute properly
7. **Automated Scheduling**: Celery Beat integration

### 📊 Performance Metrics

**Old Configuration** (5m, tight stops):
- Win Rate: 10-16%
- ROI: Negative
- Too many false signals

**New Configuration** (1d/4h, wide stops):
- Win Rate: 50% (DOGEUSDT 1d)
- ROI: +0.78% to +0.98%
- Better signal quality

## Why Breathing Room Matters

### Problem with Tight Stops
```
Entry: $100
Stop Loss (1.5x ATR): $98.50 (-1.5%)
❌ Gets stopped out by normal volatility
```

### Solution: Wider Stops
```
Entry: $100
Stop Loss (3.0x ATR): $97.00 (-3.0%)
✅ Survives normal volatility
✅ Gives trade room to move favorably
```

### Mathematical Analysis

For a 1:2.7 risk/reward ratio (3.0x SL, 8.0x TP):
- **Breakeven Win Rate**: ~27%
- **Current Win Rate**: 50%
- **Expected Profit**: Positive!

```
Win Rate × TP = (1 - Win Rate) × SL
0.50 × 8.0 = 0.50 × 3.0
4.0 > 1.5 ✅ Profitable!
```

## Technical Details

### Signal Detection
1. Get top 200 pairs by 24h volume
2. Fetch historical candles for timeframe
3. Calculate indicators (RSI, ADX, ATR, EMA, etc.)
4. Apply breathing room config
5. Generate signals when conditions met
6. Save to database if not duplicate

### Database Model
- **Model**: `Signal` (not `TradingSignal`)
- **Fields**: symbol, signal_type, entry_price, stop_loss, take_profit, confidence, timeframe, status
- **Status**: ACTIVE, CLOSED, INVALIDATED

## Future Enhancements

### Phase 2 (Next Steps)
1. **Multi-Timeframe Confirmation**: Only take 4h signals aligned with 1d trend
2. **Symbol-Specific Tuning**: Optimize parameters per volatility class
3. **Paper Trading Validation**: Test with paper trading before live
4. **Live Performance Monitoring**: Track actual vs expected performance

### Phase 3 (Advanced)
1. **Adaptive Parameters**: Auto-adjust based on market conditions
2. **Machine Learning**: Optimize entry/exit timing
3. **Risk Management**: Position sizing based on volatility
4. **Multi-Symbol Portfolio**: Diversification across assets

## Troubleshooting

### Issue: No Signals Generated
**Cause**: Network connectivity to Binance API
**Solution**: Check Docker network, VPN, or firewall settings

### Issue: Tasks Not Executing
**Cause**: Celery worker not listening to correct queues
**Solution**: Restart Celery workers
```bash
docker-compose restart celery celery-beat
```

### Issue: Duplicate Signals
**Cause**: Same signal created multiple times
**Solution**: Database check prevents duplicates (by symbol + signal_type + ACTIVE status)

## Files Modified

### New Files
- `backend/scanner/tasks/multi_timeframe_scanner.py`
- `backend/test_multi_timeframe.py`
- `backend/download_2year_data.py`
- `backend/test_breathing_room.py`

### Updated Files
- `backend/config/celery.py` - Added 1d/4h scan schedules
- `backend/scanner/services/historical_data_fetcher.py` - Fixed CSV column compatibility
- `docker/docker-compose.yml` - Added backtesting queue to Celery worker

## References

- **Breathing Room Results**: `backend/backtest_data/high/dodge/breathing_room_results_1762245589.json`
- **2-Year Backtest**: See logs showing 157 trades on BTCUSDT 1h
- **OPT6 Parameters**: Original optimized config (1.5x ATR) - now superseded by breathing room configs

## Conclusion

The system is now configured for **higher quality, lower frequency signals** using 4-hour and 1-day timeframes with **breathing room stop losses**. This approach prioritizes win rate over trade frequency, resulting in better overall profitability.

**Status**: ✅ **Ready for Paper Trading**

---

*Last Updated: November 4, 2025*
*Contact: See main README for support*
