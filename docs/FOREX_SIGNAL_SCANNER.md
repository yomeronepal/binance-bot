# Forex Signal Scanner Documentation

Complete guide to using the Forex signal scanning system for generating automated forex trading signals.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Forex Pairs Supported](#forex-pairs-supported)
4. [Signal Configurations](#signal-configurations)
5. [Running the Scanner](#running-the-scanner)
6. [Periodic Tasks](#periodic-tasks)
7. [Data Provider Integration](#data-provider-integration)
8. [Signal Format](#signal-format)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Forex Signal Scanner is a Celery-based task system that analyzes currency pairs across multiple timeframes and generates high-confidence trading signals using technical indicators.

**Key Features:**
- Multi-timeframe analysis (15m, 1h, 4h, 1d)
- Signal prioritization (higher timeframes override lower)
- Duplicate prevention
- Forex-specific configurations
- Support for major, minor, and exotic pairs

**Location:** `backend/scanner/tasks/forex_scanner.py`

---

## Features

### 1. **Multi-Timeframe Scanning**
Scans forex pairs on different timeframes:
- **15m**: Scalping (quick trades)
- **1h**: Day trading
- **4h**: Swing trading
- **1d**: Position trading

### 2. **Signal Prioritization**
Higher timeframe signals automatically replace lower timeframe signals:
```
1d (Priority 4) > 4h (Priority 3) > 1h (Priority 2) > 15m (Priority 1)
```

### 3. **Forex-Optimized Parameters**
Custom signal configurations tailored for forex:
- Tighter stop losses (forex has lower volatility)
- Adjusted ADX thresholds
- Pip-based targeting
- Higher confidence requirements for faster timeframes

### 4. **Duplicate Prevention**
Prevents creating duplicate signals for the same pair/direction.

---

## Forex Pairs Supported

### Major Pairs (7 pairs - Highest Liquidity)
```python
EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD
```
- Tightest spreads
- Best for beginners
- Most liquid

### Minor Pairs (18 cross pairs - Medium Liquidity)
```python
EURGBP, EURJPY, EURCHF, EURAUD, EURCAD, EURNZD
GBPJPY, GBPCHF, GBPAUD, GBPCAD, GBPNZD
AUDJPY, AUDCHF, AUDCAD, AUDNZD
CADJPY, CHFJPY, NZDJPY
```
- No USD involved
- Moderate spreads
- Good for experienced traders

### Exotic Pairs (9 pairs - Lower Liquidity)
```python
USDTRY, USDZAR, USDMXN, USDSEK, USDNOK
EURZAR, EURTRY, GBPTRY, JPYTRY
```
- Wider spreads
- Higher volatility
- Advanced traders only

---

## Signal Configurations

### Daily Timeframe (1d) - Position Trading
```python
min_confidence=0.70
long_adx_min=25.0    # Higher ADX for stronger trends
sl_atr_multiplier=2.0   # 2x ATR stop loss
tp_atr_multiplier=6.0   # 1:3 risk/reward
signal_expiry=1440 minutes (24 hours)
```

### 4-Hour Timeframe (4h) - Swing Trading
```python
min_confidence=0.70
long_adx_min=22.0
sl_atr_multiplier=1.8
tp_atr_multiplier=5.5   # 1:3.05 risk/reward
signal_expiry=480 minutes (8 hours)
```

### 1-Hour Timeframe (1h) - Day Trading
```python
min_confidence=0.72    # Higher confidence
long_adx_min=20.0
sl_atr_multiplier=1.5
tp_atr_multiplier=4.5   # 1:3 risk/reward
signal_expiry=180 minutes (3 hours)
```

### 15-Minute Timeframe (15m) - Scalping
```python
min_confidence=0.75    # Highest confidence
long_adx_min=18.0
sl_atr_multiplier=1.2
tp_atr_multiplier=3.6   # 1:3 risk/reward
signal_expiry=60 minutes (1 hour)
```

---

## Running the Scanner

### Method 1: Management Command (Recommended for Testing)

#### Scan Major Pairs (Default)
```bash
docker exec binancebot_web python manage.py scan_forex
# or
docker exec binancebot_web python manage.py scan_forex --mode major
```

**Output:**
- Scans 7 major forex pairs
- Timeframes: 4h and 1d
- Synchronous execution (shows results immediately)

#### Scan All Pairs
```bash
docker exec binancebot_web python manage.py scan_forex --mode all
```

**Output:**
- Scans 25 pairs (major + minor)
- Timeframes: 1h, 4h, and 1d
- Higher chance of finding signals

#### Scan for Scalping
```bash
docker exec binancebot_web python manage.py scan_forex --mode scalping
```

**Output:**
- Scans 7 major pairs
- Timeframes: 15m and 1h
- Fast timeframes for quick trades

#### Custom Scan
```bash
docker exec binancebot_web python manage.py scan_forex --mode custom \
  --timeframes 1h 4h \
  --pairs major minor
```

**Options:**
- `--timeframes`: 15m, 1h, 4h, 1d (space-separated)
- `--pairs`: major, minor, exotic (space-separated)

#### Async Execution (via Celery)
```bash
docker exec binancebot_web python manage.py scan_forex --async
```

**Use when:**
- Running long scans (all pairs)
- Don't want to wait for results
- Monitor: `docker logs binancebot_celery -f`

---

### Method 2: Python/Django Shell

```python
from scanner.tasks.forex_scanner import scan_major_forex_pairs

# Synchronous
result = scan_major_forex_pairs()
print(result)

# Asynchronous (via Celery)
task = scan_major_forex_pairs.delay()
print(f"Task ID: {task.id}")

# Check task status
from celery.result import AsyncResult
result = AsyncResult(task.id)
print(result.status)  # PENDING, STARTED, SUCCESS, FAILURE
print(result.result)  # Get result when complete
```

---

### Method 3: API Endpoint (Create One)

You can create a Django REST API endpoint to trigger scans from the frontend.

---

## Periodic Tasks

Forex scanning runs automatically via Celery Beat.

### Current Schedule

**Major Forex Pairs (4h and 1d):**
```python
'scan-major-forex-pairs': Every 4 hours at :15 minutes
# Runs at: 00:15, 04:15, 08:15, 12:15, 16:15, 20:15
```

**Forex Scalping (15m and 1h):**
*Currently disabled - uncomment in `config/celery.py` to enable*
```python
# 'scan-forex-scalping': Every hour at :30 minutes
```

### Enable/Disable Periodic Tasks

**Edit:** `backend/config/celery.py`

**To enable scalping:**
```python
# Uncomment this block (lines 73-79)
'scan-forex-scalping': {
    'task': 'scanner.tasks.scan_forex_scalping',
    'schedule': crontab(minute=30),
    'options': {'expires': 3000.0}
},
```

**To change schedule:**
```python
'scan-major-forex-pairs': {
    'task': 'scanner.tasks.scan_major_forex_pairs',
    'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours at :00
    'options': {'expires': 3000.0}
},
```

**Restart Celery Beat:**
```bash
docker restart binancebot_celery_beat
```

---

## Data Provider Integration

### Current Status: ⚠️ **Mock Data Provider**

The scanner currently uses a placeholder `ForexDataProvider` class that returns empty data.

**Location:** `backend/scanner/tasks/forex_scanner.py` (Line 110)

### Integration Steps

#### Option 1: OANDA API (Recommended)
```python
import oandapyV20
from oandapyV20 import API
import oandapyV20.endpoints.instruments as instruments

class ForexDataProvider:
    def __init__(self):
        self.client = API(access_token=os.getenv('OANDA_API_TOKEN'))

    async def get_klines(self, symbol: str, interval: str, limit: int = 200):
        # Map timeframe
        granularity_map = {
            '15m': 'M15',
            '1h': 'H1',
            '4h': 'H4',
            '1d': 'D'
        }
        granularity = granularity_map.get(interval, 'H4')

        # Request candles
        params = {
            'count': limit,
            'granularity': granularity
        }

        r = instruments.InstrumentsCandles(instrument=symbol, params=params)
        self.client.request(r)

        # Convert to Binance-compatible format
        klines = []
        for candle in r.response['candles']:
            klines.append([
                int(candle['time'][:10]) * 1000,  # Open time (ms)
                float(candle['mid']['o']),         # Open
                float(candle['mid']['h']),         # High
                float(candle['mid']['l']),         # Low
                float(candle['mid']['c']),         # Close
                float(candle['volume']),           # Volume
                0, 0, 0, 0, 0                      # Placeholder fields
            ])

        return klines
```

#### Option 2: Alpha Vantage (Free Tier)
```python
import requests

class ForexDataProvider:
    def __init__(self):
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY')

    async def get_klines(self, symbol: str, interval: str, limit: int = 200):
        # Map symbol: EURUSD -> EUR, USD
        from_currency = symbol[:3]
        to_currency = symbol[3:]

        # Map interval
        function_map = {
            '15m': 'FX_INTRADAY',
            '1h': 'FX_INTRADAY',
            '4h': 'FX_INTRADAY',
            '1d': 'FX_DAILY'
        }

        url = f'https://www.alphavantage.co/query'
        params = {
            'function': function_map.get(interval),
            'from_symbol': from_currency,
            'to_symbol': to_currency,
            'interval': interval if interval != '1d' else None,
            'apikey': self.api_key,
            'outputsize': 'full'
        }

        response = requests.get(url, params=params)
        data = response.json()

        # Parse and convert to klines format
        # ... implementation
```

#### Option 3: FXCM REST API
```python
import fxcmpy

class ForexDataProvider:
    def __init__(self):
        self.connection = fxcmpy.fxcmpy(
            access_token=os.getenv('FXCM_API_TOKEN'),
            log_level='error'
        )

    async def get_klines(self, symbol: str, interval: str, limit: int = 200):
        # Get candles
        candles = self.connection.get_candles(
            symbol,
            period=interval,
            number=limit
        )

        # Convert to klines format
        # ... implementation
```

---

## Signal Format

Forex signals are saved to the database with this structure:

```python
{
    'symbol': 'EURUSD',              # Currency pair
    'direction': 'LONG',             # LONG (BUY) or SHORT (SELL)
    'entry': 1.08500,                # Entry price (5 decimals)
    'sl': 1.08200,                   # Stop loss
    'tp': 1.09100,                   # Take profit
    'confidence': 0.85,              # 85% confidence
    'timeframe': '4h',               # Signal timeframe
    'market_type': 'FOREX',          # Market type
    'leverage': 100,                 # Default 100x leverage
    'status': 'ACTIVE'               # Signal status
}
```

### Viewing Signals

**Database:**
```bash
docker exec binancebot_web python manage.py shell
from signals.models import Signal
forex_signals = Signal.objects.filter(market_type='FOREX', status='ACTIVE')
for signal in forex_signals:
    print(f"{signal.symbol}: {signal.direction} @ {signal.entry}")
```

**Admin Panel:**
```
http://localhost:8000/admin/signals/signal/
Filter by: market_type = FOREX
```

**Frontend:**
```
http://localhost:5173/forex
```

---

## Troubleshooting

### Issue: "No forex signals created"

**Cause:** Forex data provider returns empty data (mock implementation)

**Solution:** Integrate a real forex data provider (see [Data Provider Integration](#data-provider-integration))

---

### Issue: "Task not found" error

**Cause:** Celery worker hasn't loaded the forex_scanner module

**Solution:**
```bash
docker restart binancebot_celery binancebot_celery_beat
docker logs binancebot_celery --tail 50
```

Look for: `[tasks]` section showing `scanner.tasks.scan_major_forex_pairs`

---

### Issue: Duplicate signals created

**Cause:** Signal prioritization not working

**Check:**
```python
from signals.models import Signal
duplicates = Signal.objects.filter(
    symbol__symbol='EURUSD',
    direction='LONG',
    market_type='FOREX',
    status='ACTIVE'
)
print(f"Found {duplicates.count()} signals")
```

**Expected:** 1 signal per direction per symbol
**If > 1:** Check `save_forex_signal()` function logic

---

### Issue: Signals expire too quickly

**Cause:** Short expiry time in configuration

**Solution:** Adjust `signal_expiry_minutes` in `FOREX_CONFIGS`

```python
FOREX_CONFIGS = {
    '4h': SignalConfig(
        signal_expiry_minutes=480,  # Increase this (currently 8 hours)
        ...
    )
}
```

---

### Issue: Low confidence signals not created

**Cause:** `min_confidence` threshold too high

**Check:** Current thresholds:
- 15m: 0.75 (75%)
- 1h: 0.72 (72%)
- 4h: 0.70 (70%)
- 1d: 0.70 (70%)

**Solution:** Lower thresholds if needed (not recommended < 0.65)

---

## Next Steps

1. **Integrate Real Data Provider**
   - Sign up for OANDA/Alpha Vantage/FXCM
   - Get API key
   - Implement `ForexDataProvider.get_klines()`

2. **Test Scanner**
   ```bash
   docker exec binancebot_web python manage.py scan_forex --mode major
   ```

3. **Enable Periodic Scanning**
   - Uncomment `scan-major-forex-pairs` in `config/celery.py`
   - Restart Celery Beat

4. **Monitor Results**
   - Check `/forex` page in frontend
   - View signals in admin panel
   - Monitor Celery logs

5. **Paper Trade Forex Signals**
   - Signals automatically create paper trades
   - Track performance in Bot Performance dashboard

---

## Files Modified/Created

**New Files:**
- `backend/scanner/tasks/forex_scanner.py` - Main scanner implementation
- `backend/scanner/management/commands/scan_forex.py` - Management command
- `docs/FOREX_SIGNAL_SCANNER.md` - This documentation

**Modified Files:**
- `backend/scanner/tasks/__init__.py` - Registered forex tasks
- `backend/config/celery.py` - Added periodic task schedule
- `backend/signals/models.py` - Added FOREX market type (already done)
- Frontend files - Added forex pages and components (already done)

---

## Support

For issues or questions:
1. Check this documentation
2. Review `backend/scanner/tasks/forex_scanner.py` code
3. Check Celery logs: `docker logs binancebot_celery -f`
4. Consult main project README

---

**Last Updated:** 2025-11-05
**Version:** 1.0
**Status:** ✅ Implemented (Awaiting Data Provider Integration)
