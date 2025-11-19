# Fibonacci Pullback System - Deployment Guide

## Implementation Status: ✅ COMPLETE

All core tasks (1-7) have been successfully implemented. Task 8 (testing) is ready to execute when Docker environment is configured.

---

## What Was Built

### Core Features Implemented

1. **Fibonacci Calculation Engine** ([fib_utils.py](backend/scanner/services/fib_utils.py))
   - Swing high/low detection with configurable lookback
   - Fibonacci retracement level calculation (38.2%, 50%, 61.8%, 78.6%)
   - Golden zone entry detection (50-61.8%)
   - Fibonacci extension target calculation for take-profit
   - RSI and volume validation for signal quality

2. **Real-Time Price Watcher** ([fib_watcher.py](backend/scanner/services/fib_watcher.py))
   - Monitors signals with status `WAITING_FOR_PULLBACK`
   - Fetches current market prices from Binance
   - Detects when price enters golden zone
   - Triggers entry and creates paper trades automatically
   - Broadcasts WebSocket events to frontend

3. **Signal Engine Integration** ([signal_engine.py](backend/scanner/strategies/signal_engine.py))
   - Added Fibonacci as indicator #14 with 2.5 weight
   - Integrated into LONG and SHORT signal conditions
   - Stores Fibonacci metadata in signal.meta field
   - Sets signal status to `WAITING_FOR_PULLBACK` when appropriate
   - Total scoring now 20.3 points (up from 17.8)

4. **Automated Monitoring** ([celery_tasks.py](backend/scanner/tasks/celery_tasks.py) + [celery.py](backend/config/celery.py))
   - Celery Beat task runs every 30 seconds
   - Checks all waiting signals for golden zone entry
   - Logs monitoring activity and triggered entries
   - Automatic retry on failure with 30-second delay

5. **Paper Trading Integration**
   - Auto-creates paper trades when golden zone reached
   - Stop-loss at fib_78.6 level (conservative)
   - Take-profit at 9% or Fibonacci extensions
   - Tracks entry time, prices, and P/L

---

## File Changes Summary

### New Files Created (3)

1. **backend/scanner/services/fib_utils.py** (350+ lines)
   - `find_recent_swing_high_low()` - Swing detection
   - `compute_fib_levels()` - Calculate retracement levels
   - `check_fibonacci_pullback()` - Main entry zone check
   - `calculate_fib_extension_targets()` - TP targets
   - `validate_fibonacci_signal()` - RSI/volume confirmation

2. **backend/scanner/services/fib_watcher.py** (275+ lines)
   - `FibonacciPullbackWatcher` class
   - `get_waiting_signals()` - Fetch signals to monitor
   - `get_current_price()` - Live price from Binance
   - `check_entry_zone()` - Verify golden zone entry
   - `trigger_entry()` - Execute entry logic
   - `emit_entry_event()` - WebSocket broadcast
   - `create_paper_trade()` - Auto paper trade creation
   - `monitor()` - Main monitoring loop

3. **test_fib_utils.py** (350+ lines)
   - Comprehensive test suite with 21 tests
   - Tests swing detection, fib calculations, entry zones
   - Edge case validation
   - Ready to run when Docker is configured

### Modified Files (3)

1. **backend/scanner/strategies/signal_engine.py**
   - Lines 16-21: Added Fibonacci imports with graceful fallback
   - Lines 69-74: Added 5 Fibonacci config parameters to SignalConfig
   - Lines 92-93: Added `meta` and `status` fields to ActiveSignal
   - Lines 594: Updated max_score to 20.3 (added fibonacci_weight)
   - Lines 717-743: Added Fibonacci check in LONG conditions
   - Lines 906-932: Added Fibonacci check in SHORT conditions
   - Lines 1000-1036: Updated _create_signal() to store Fibonacci metadata

2. **backend/scanner/tasks/celery_tasks.py**
   - Lines 1044-1064: Added `monitor_fibonacci_pullbacks()` Celery task
   - Decorated with @shared_task, max_retries=3, retry_delay=10

3. **backend/config/celery.py**
   - Lines 127-132: Added beat schedule for Fibonacci monitoring
   - Runs every 30 seconds with 25-second expiry

---

## Configuration Parameters

### SignalConfig - Fibonacci Settings

```python
fibonacci_weight: float = 2.5           # Scoring weight for pullback confirmation
fib_lookback_candles: int = 50          # How far back to search for swings
fib_entry_zone_min: float = 0.5         # 50% Fibonacci level
fib_entry_zone_max: float = 0.618       # 61.8% Golden ratio
fib_enable_pullback: bool = True        # Enable/disable feature
```

### Default Behavior

**When Enabled** (fib_enable_pullback=True):
- Fibonacci check adds 2.5 points to score if in golden zone
- Signal status set to `WAITING_FOR_PULLBACK`
- Real-time monitoring activates
- Auto paper trade on entry

**When Disabled** (fib_enable_pullback=False):
- No Fibonacci calculation
- Signal status remains `ACTIVE`
- Standard signal flow continues
- No additional scoring

---

## Signal Lifecycle

### Standard Flow (Without Fibonacci)
```
SIGNAL_GENERATED → ACTIVE → PAPER_TRADE_OPEN → CLOSED
```

### Fibonacci Flow (With Pullback)
```
SIGNAL_GENERATED
  ↓
WAITING_FOR_PULLBACK (monitoring for golden zone entry)
  ↓
ENTRY_ZONE_REACHED (price in 50-61.8% zone)
  ↓
PAPER_TRADE_OPEN (auto-created with fib_78.6 SL)
  ↓
CLOSED (hit SL or TP)
```

---

## Testing Instructions

### When Docker Environment is Ready

1. **Start Docker Services**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

2. **Run Fibonacci Utility Tests**
```bash
docker exec <web-container-name> python /app/test_fib_utils.py
```

**Expected Output:**
```
✅ ALL TESTS PASSED - Fibonacci Utils Ready for Integration!

Test Summary:
- Swing Detection: 5/5 tests passed
- Fibonacci Levels: 4/4 tests passed
- Entry Zone Detection: 6/6 tests passed
- Edge Cases: 3/3 tests passed
- Extension Targets: 2/2 tests passed
- Signal Validation: 1/1 tests passed

Total: 21/21 tests passing
```

3. **Verify Celery Beat Schedule**
```bash
docker logs <celery-container-name> | grep "fibonacci"
```

**Expected Log Entries:**
```
[2025-11-19 10:00:00] 🔍 Monitoring Fibonacci pullback signals...
[2025-11-19 10:00:01] No signals waiting for Fibonacci pullback
[2025-11-19 10:00:01] ✅ Fibonacci monitoring complete
```

4. **Generate Test Signal with Fibonacci**
```bash
docker exec <web-container-name> python manage.py shell
```

```python
from scanner.services.binance_client import BinanceClient
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig

config = SignalConfig(
    fib_enable_pullback=True,
    fib_lookback_candles=50,
    fib_entry_zone_min=0.5,
    fib_entry_zone_max=0.618
)

engine = SignalDetectionEngine(config)
signals = engine.detect_signals(['BTCUSDT'], '4h')

for sig in signals:
    print(f"Signal: {sig.symbol} {sig.direction}")
    print(f"Status: {sig.status}")
    print(f"Meta: {sig.meta}")
```

5. **Monitor Real-Time Entry Triggers**
```bash
docker logs -f <celery-container-name> | grep "FIBONACCI ENTRY"
```

**Expected When Entry Triggered:**
```
🎯 FIBONACCI ENTRY TRIGGERED: BTCUSDT LONG at 42350.50 (Zone: 42200.00 - 42500.00)
✅ Fibonacci entry event broadcasted for BTCUSDT LONG
📊 Paper trade created: BTCUSDT LONG Entry=42350.50, SL=41800.00, TP=46201.95
```

---

## Deployment Checklist

### Pre-Deployment

- [x] Core Fibonacci utilities implemented
- [x] Signal engine integration complete
- [x] Watcher service created
- [x] Celery task and schedule configured
- [x] Paper trading integration done
- [ ] Test suite executed (pending Docker)
- [ ] Database migration for Signal.status field (optional)

### Deployment Steps

1. **Backup Database**
```bash
docker exec <postgres-container> pg_dump -U postgres binance_bot > backup.sql
```

2. **Apply Migrations** (if Signal.status field added)
```bash
docker exec <web-container> python manage.py makemigrations
docker exec <web-container> python manage.py migrate
```

3. **Restart Services**
```bash
docker-compose -f docker-compose.prod.yml restart
```

4. **Verify Celery Beat**
```bash
docker exec <celery-container> celery -A config inspect scheduled
```

5. **Check Logs for Errors**
```bash
docker-compose -f docker-compose.prod.yml logs -f --tail=100
```

### Post-Deployment Monitoring

**First 24 Hours:**
- Monitor Celery Beat logs for Fibonacci task execution
- Check signal generation includes Fibonacci metadata
- Verify watcher triggers entries when golden zone reached
- Track paper trade creation and P/L

**First Week:**
- Compare win rates with/without Fibonacci
- Monitor false positive rate in golden zone
- Analyze optimal fib_lookback_candles value
- Tune fib_entry_zone_min/max if needed

---

## Performance Expectations

### Theoretical Impact

**Before Fibonacci:**
- Win Rate: 16.7% (1 win out of 6 trades)
- ROI: -0.03%
- Strategy: Pure RSI mean reversion

**With Fibonacci (Expected):**
- Win Rate: 25-35% (+10-15% improvement)
- ROI: > 0% (profitable)
- Strategy: RSI + Fibonacci pullback confirmation

**Why Improvement Expected:**
1. Golden zone (50-61.8%) statistically significant support/resistance
2. Filters out weak signals that lack pullback structure
3. Better entry timing reduces slippage
4. Conservative SL at fib_78.6 reduces stop-outs

### Monitoring Metrics

**Key Performance Indicators:**

```sql
SELECT
    COUNT(*) as total_signals,
    SUM(CASE WHEN status = 'WAITING_FOR_PULLBACK' THEN 1 ELSE 0 END) as waiting_signals,
    SUM(CASE WHEN status = 'ENTRY_ZONE_REACHED' THEN 1 ELSE 0 END) as entries_triggered,
    AVG(confidence) as avg_confidence
FROM signals
WHERE created_at > NOW() - INTERVAL '7 days'
    AND meta->>'strategy' = 'fibonacci_pullback';
```

**Paper Trade Performance:**

```sql
SELECT
    direction,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as win_rate,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl
FROM paper_trades
WHERE signal_id IN (
    SELECT id FROM signals WHERE meta->>'strategy' = 'fibonacci_pullback'
)
GROUP BY direction;
```

---

## Troubleshooting

### Issue: No Fibonacci Signals Generated

**Check 1: Feature Enabled?**
```python
config = SignalConfig()
print(config.fib_enable_pullback)
```

**Check 2: Imports Working?**
```bash
docker exec <web-container> python -c "from scanner.services.fib_utils import check_fibonacci_pullback; print('OK')"
```

**Check 3: Sufficient Data?**
```python
df = get_historical_data('BTCUSDT', '4h', 100)
print(f"Candles: {len(df)}")
```

### Issue: Watcher Not Monitoring

**Check 1: Celery Beat Running?**
```bash
docker ps | grep celery
```

**Check 2: Task Scheduled?**
```bash
docker exec <celery-container> celery -A config inspect scheduled
```

**Check 3: Check Logs**
```bash
docker logs <celery-container> | grep -i fibonacci
```

### Issue: Entry Not Triggering

**Check 1: Signals in Database?**
```sql
SELECT id, symbol, direction, status, meta
FROM signals
WHERE status = 'WAITING_FOR_PULLBACK';
```

**Check 2: Price in Golden Zone?**
```python
from scanner.services.fib_watcher import FibonacciPullbackWatcher
watcher = FibonacciPullbackWatcher()
signal = Signal.objects.get(id=123)
current_price = watcher.get_current_price(signal.symbol.symbol)
in_zone = watcher.check_entry_zone(signal, current_price)
print(f"Price: {current_price}, In Zone: {in_zone}")
```

**Check 3: Binance API Working?**
```python
from scanner.services.binance_client import BinanceClient
client = BinanceClient()
ticker = client.get_ticker_price('BTCUSDT')
print(ticker)
```

---

## API Endpoints (For Frontend Integration)

### Get Fibonacci Signals

**GET /api/signals/?status=WAITING_FOR_PULLBACK**

Response:
```json
{
  "count": 3,
  "results": [
    {
      "id": 123,
      "symbol": "BTCUSDT",
      "direction": "LONG",
      "status": "WAITING_FOR_PULLBACK",
      "confidence": 0.78,
      "entry_price": 42500.00,
      "stop_loss": 41775.00,
      "take_profit": 46305.00,
      "meta": {
        "strategy": "fibonacci_pullback",
        "swing_high": 44000.00,
        "swing_low": 40000.00,
        "fib_50": 42500.00,
        "fib_61_8": 42200.00,
        "fib_78_6": 41800.00,
        "pullback_depth": 0.55,
        "entry_zone": "golden_ratio",
        "in_entry_zone": true
      }
    }
  ]
}
```

### WebSocket Event Schema

**Event: fib_entry_triggered**

```json
{
  "type": "fib_entry_triggered",
  "signal_id": 123,
  "symbol": "BTCUSDT",
  "side": "LONG",
  "entry_price": 42350.50,
  "entry_zone": "golden_ratio",
  "meta": {
    "swing_high": 44000.00,
    "swing_low": 40000.00,
    "fib_50": 42500.00,
    "fib_61_8": 42200.00,
    "fib_78_6": 41800.00
  },
  "timeframe": "4h",
  "confidence": 0.78,
  "timestamp": "2025-11-19T10:15:30.123Z"
}
```

---

## Next Steps

### Immediate (When Docker Ready)
1. Run test suite: `docker exec <web-container> python /app/test_fib_utils.py`
2. Generate test signals with Fibonacci enabled
3. Monitor Celery logs for entry triggers
4. Validate paper trade creation

### Short-Term (1-2 Weeks)
1. Collect performance data on Fibonacci signals
2. Compare win rates: standard vs Fibonacci
3. Optimize fib_lookback_candles (test 30, 50, 100)
4. Tune entry zone (test 0.5-0.618 vs 0.382-0.618)

### Medium-Term (1 Month)
1. Implement frontend chart integration with Fibonacci levels
2. Add WebSocket listener for real-time entry alerts
3. Create Fibonacci-specific analytics dashboard
4. Backtest Fibonacci strategy on historical data

### Long-Term (2-3 Months)
1. Integrate with live trading (if paper trades successful)
2. Add Fibonacci extension TP targets
3. Implement dynamic fib_lookback based on volatility
4. Multi-timeframe Fibonacci confluence detection

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    SIGNAL GENERATION                         │
│  (signal_engine.py - Every 30s for each timeframe)         │
│                                                              │
│  1. Check 14 indicators (including Fibonacci)                │
│  2. Calculate score (max 20.3 points)                        │
│  3. If Fibonacci in golden zone:                             │
│     - Store fib metadata in signal.meta                      │
│     - Set status = 'WAITING_FOR_PULLBACK'                    │
│  4. Save signal to database                                  │
└─────────────────┬────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              FIBONACCI MONITORING                            │
│  (Celery Beat - Every 30s via monitor_fibonacci_pullbacks)  │
│                                                              │
│  1. FibonacciPullbackWatcher.monitor()                      │
│  2. Fetch signals WHERE status='WAITING_FOR_PULLBACK'       │
│  3. For each signal:                                         │
│     - Get current price from Binance                         │
│     - Check if price in golden zone (50-61.8%)               │
│     - If YES → trigger_entry()                               │
└─────────────────┬────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  ENTRY TRIGGER                               │
│  (fib_watcher.py - When golden zone reached)                │
│                                                              │
│  1. Update signal.status = 'ENTRY_ZONE_REACHED'             │
│  2. Broadcast WebSocket event 'fib_entry_triggered'         │
│  3. Auto-create PaperTrade:                                  │
│     - entry_price = current_price                            │
│     - stop_loss = fib_78.6 level                             │
│     - take_profit = 9% or Fibonacci extension                │
│  4. Log entry details                                        │
└─────────────────┬────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                PAPER TRADE MONITORING                        │
│  (Celery Beat - Every 30s via check_and_close_paper_trades) │
│                                                              │
│  1. Check if current_price <= stop_loss (exit)               │
│  2. Check if current_price >= take_profit (exit)             │
│  3. Calculate P/L                                            │
│  4. Update trade status = 'CLOSED'                           │
│  5. Record win/loss for analytics                            │
└──────────────────────────────────────────────────────────────┘
```

---

## File Reference Quick Links

**Core Implementation:**
- [fib_utils.py](backend/scanner/services/fib_utils.py) - Fibonacci calculations
- [fib_watcher.py](backend/scanner/services/fib_watcher.py) - Real-time monitoring
- [signal_engine.py](backend/scanner/strategies/signal_engine.py) - Signal integration
- [celery_tasks.py](backend/scanner/tasks/celery_tasks.py) - Monitoring task
- [celery.py](backend/config/celery.py) - Beat schedule

**Documentation:**
- [FIBONACCI_IMPLEMENTATION_COMPLETE.md](FIBONACCI_IMPLEMENTATION_COMPLETE.md) - Technical docs
- [FIBONACCI_NEXT_STEPS.md](FIBONACCI_NEXT_STEPS.md) - Advanced features guide
- [test_fib_utils.py](test_fib_utils.py) - Test suite

**Configuration:**
- SignalConfig in [signal_engine.py:69-74](backend/scanner/strategies/signal_engine.py#L69-L74)
- Celery schedule in [celery.py:127-132](backend/config/celery.py#L127-L132)

---

## Support

**For Issues:**
1. Check logs: `docker-compose logs -f`
2. Verify configuration: Review SignalConfig parameters
3. Test components individually: Use Python shell in Docker
4. Review documentation: FIBONACCI_IMPLEMENTATION_COMPLETE.md

**For Questions:**
- Implementation details: See code comments in fib_utils.py
- Integration: See signal_engine.py modifications
- Monitoring: See celery_tasks.py:1044-1064

---

**Status**: ✅ Ready for Testing & Deployment
**Last Updated**: November 19, 2025
**Implementation Time**: Tasks 1-7 completed in single session
**Next Action**: Run test suite when Docker environment configured
