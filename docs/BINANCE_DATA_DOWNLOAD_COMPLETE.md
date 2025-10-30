# Binance Historical Data Download - Complete

**Date**: October 30, 2025
**Status**: Successfully Downloaded

---

## Summary

Successfully downloaded **30 days of 5-minute historical data** from Binance USDⓈ-M Futures for 5 symbols across all volatility levels.

---

## Downloaded Data

### High Volatility (1 symbol)
- **DOGEUSDT**: 8,928 candles (0.71 MB)
  - Date range: Dec 1, 2024 - Jan 1, 2025
  - File: `backtest_data/high/DOGEUSDT_5m.csv`

### Medium Volatility (2 symbols)
- **SOLUSDT**: 8,928 candles (0.63 MB)
  - Date range: Dec 1, 2024 - Jan 1, 2025
  - File: `backtest_data/medium/SOLUSDT_5m.csv`

- **ADAUSDT**: 8,928 candles (0.65 MB)
  - Date range: Dec 1, 2024 - Jan 1, 2025
  - File: `backtest_data/medium/ADAUSDT_5m.csv`

### Low Volatility (2 symbols)
- **BTCUSDT**: 8,928 candles (0.70 MB)
  - Date range: Dec 1, 2024 - Jan 1, 2025
  - File: `backtest_data/low/BTCUSDT_5m.csv`

- **ETHUSDT**: 8,928 candles (0.70 MB)
  - Date range: Dec 1, 2024 - Jan 1, 2025
  - File: `backtest_data/low/ETHUSDT_5m.csv`

---

## Data Statistics

| Metric | Value |
|--------|-------|
| **Total Symbols** | 5 |
| **Total Candles** | 44,640 (8,928 per symbol) |
| **Total File Size** | ~3.39 MB |
| **Timeframe** | 5-minute |
| **Period** | 30 days (Dec 1, 2024 - Jan 1, 2025) |
| **Futures Type** | USDⓈ-M (USDT-margined) |
| **Data Source** | Binance Vision (official historical data) |

---

## Data Format

Each CSV file contains the following columns:

```csv
datetime,open,high,low,close,volume,quote_volume,trades
2024-12-01T05:45:00,0.42179,0.42428,0.42105,0.42362,25810411.0,10904006.72921,15933
```

**Column Descriptions**:
- `datetime`: ISO 8601 timestamp (UTC+5:45 timezone)
- `open`: Opening price
- `high`: Highest price in 5-minute period
- `low`: Lowest price in 5-minute period
- `close`: Closing price
- `volume`: Base asset volume (e.g., DOGE, SOL, BTC)
- `quote_volume`: Quote asset volume (USDT)
- `trades`: Number of trades in the 5-minute period

---

## Issues Encountered & Resolved

### 1. Unicode Encoding Error
**Problem**: Emoji characters (✅, ❌, ⏭️) couldn't be displayed in Windows console
**Solution**: Replaced all emojis with ASCII equivalents ([OK], [ERROR], [SKIP])

### 2. CSV Parsing Error
**Problem**: "invalid literal for int()" when parsing CSV data
**Solution**: Added logic to skip the header row in CSV files

### 3. Future Dates
**Problem**: Initially tried to download data from October 2025 (doesn't exist yet)
**Solution**: Changed date range to December 2024 (actual historical data)

### 4. Missing Symbols
**Problem**: PEPEUSDT and SHIBUSDT returned 404 errors
**Solution**: These symbols don't exist in Binance USDⓈ-M futures, removed from download list

---

## Download Script

**File**: `download_binance_data_simple.py`

**Features**:
- Uses only Python standard library (no external dependencies)
- Downloads from Binance Vision public data API
- Automatically creates directory structure by volatility level
- Handles 404 errors gracefully
- Removes duplicate candles
- Validates and sorts data by timestamp
- Rate-limited (0.2s delay between requests)

**Usage**:
```bash
python download_binance_data_simple.py
```

**Customization**:
Edit the script to:
- Add more symbols to `SYMBOLS` dict
- Change date range (lines 152-153)
- Change timeframe (line 22: "5m", "15m", "1h", etc.)
- Adjust output directory (line 23)

---

## Data Validation

All downloaded data was validated:
- ✓ No missing dates
- ✓ No duplicate timestamps
- ✓ Continuous 5-minute intervals
- ✓ 288 candles per day (24h * 60min / 5min = 288)
- ✓ Data sorted chronologically
- ✓ All CSV files properly formatted

---

## Next Steps

### 1. Create Simple Backtest Script
Now that you have historical data, create a backtest script to:
- Load CSV data
- Calculate RSI, ADX, ATR indicators
- Generate signals using your mean reversion strategy
- Simulate trades with proper position sizing
- Calculate win rate, profit factor, drawdowns

### 2. Test Volatility-Aware Strategy
Compare performance across volatility levels:
- **HIGH (DOGE)**: SL=2.0x, TP=3.5x, ADX=18
- **MEDIUM (SOL/ADA)**: SL=1.5x, TP=2.5x, ADX=22
- **LOW (BTC/ETH)**: SL=1.0x, TP=2.0x, ADX=20

### 3. Extend Data Range (Optional)
If you need more data for statistical significance:
```python
# Edit lines 152-153 in download_binance_data_simple.py
end_date = datetime(2024, 12, 31)
start_date = datetime(2024, 1, 1)  # Full year of 2024
```

Then re-run the script to download a full year of data.

### 4. Add More Symbols (Optional)
Add more symbols to test:
```python
SYMBOLS = {
    'HIGH': ['DOGEUSDT', '1000SHIBUSDT', '1000PEPEUSDT'],  # Note: 1000X prefix
    'MEDIUM': ['SOLUSDT', 'ADAUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT'],
    'LOW': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
}
```

**Note**: Some meme coins use "1000" prefix in futures (e.g., 1000SHIBUSDT, 1000PEPEUSDT).

---

## Files Created

1. `download_binance_data_simple.py` - Download script (uses only stdlib)
2. `backtest_data/` - Directory containing downloaded CSV files
   - `high/DOGEUSDT_5m.csv`
   - `medium/SOLUSDT_5m.csv`
   - `medium/ADAUSDT_5m.csv`
   - `low/BTCUSDT_5m.csv`
   - `low/ETHUSDT_5m.csv`
3. This documentation file

---

## Technical Details

### Binance Vision API
- **URL Format**: `https://data.binance.vision/data/futures/um/daily/klines/{SYMBOL}/{TIMEFRAME}/{SYMBOL}-{TIMEFRAME}-{DATE}.zip`
- **Example**: `https://data.binance.vision/data/futures/um/daily/klines/DOGEUSDT/5m/DOGEUSDT-5m-2024-12-01.zip`
- **Data Availability**: Daily files updated at ~00:00 UTC
- **Rate Limits**: No authentication required, reasonable rate limits
- **File Format**: ZIP containing single CSV file

### Data Quality
Binance Vision provides official, verified historical data that matches actual trading data. This is the same data used by:
- Professional trading firms
- Academic research
- Exchange APIs
- Third-party data providers

---

## Resources

**Binance Vision Documentation**:
- Main site: https://data.binance.vision/
- Futures data: https://data.binance.vision/data/futures/um/daily/klines/
- Available symbols: Browse the website to see all available futures pairs

**Alternative Download Methods**:
1. Use the full-featured script with pandas (requires `pip install requests pandas`)
2. Use Binance API directly (requires API key)
3. Use third-party libraries like `ccxt` or `python-binance`

---

## Summary

✓ **Download Complete**: 5 symbols, 30 days, 44,640 candles
✓ **Data Validated**: No errors, duplicates, or missing dates
✓ **Ready for Backtesting**: CSV files properly formatted and organized

**Total download time**: ~2 minutes
**Total data size**: 3.39 MB
**Data quality**: Excellent (official Binance data)

---

**Next Action**: Create a simple backtest script to test your mean reversion strategy on this historical data.
