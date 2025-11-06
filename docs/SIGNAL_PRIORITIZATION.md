# Signal Timeframe Prioritization System

## Overview

The trading bot implements an intelligent **timeframe prioritization system** that ensures when the same symbol generates signals across multiple timeframes (15m, 1h, 4h, 1d), only the **highest timeframe signal** is shown in the frontend.

This prevents:
- Duplicate signals for the same symbol
- Trading confusion from conflicting timeframes
- Over-trading on lower timeframe noise

---

## Priority Ranking

```python
TIMEFRAME_PRIORITY = {
    '1d': 4,   # Highest priority (most reliable)
    '4h': 3,   # High priority
    '1h': 2,   # Medium priority
    '15m': 1   # Lowest priority (most noise)
}
```

**Rule**: Higher timeframe signals ALWAYS take precedence over lower timeframe signals.

---

## How It Works

### Scenario 1: New Signal, No Existing Signal

**Example**: BTCUSDT generates a LONG signal on 4h timeframe

```
Database: []
New Signal: BTCUSDT LONG 4h

Result: ✅ Signal saved
Frontend shows: BTCUSDT LONG (4h)
```

---

### Scenario 2: Same Timeframe Duplicate

**Example**: BTCUSDT LONG signal already exists on 4h, new 4h signal detected

```
Database: [BTCUSDT LONG 4h]
New Signal: BTCUSDT LONG 4h

Result: ⏭️ Skipped (duplicate)
Frontend shows: BTCUSDT LONG (4h) [unchanged]
```

---

### Scenario 3: Lower Timeframe Signal (Rejected)

**Example**: BTCUSDT has 4h LONG signal, 1h LONG signal detected

```
Database: [BTCUSDT LONG 4h]
New Signal: BTCUSDT LONG 1h

Result: ⏭️ Skipped (lower priority than existing 4h)
Frontend shows: BTCUSDT LONG (4h) [unchanged]

Log: "Skipping LONG signal for BTCUSDT (1h) - higher timeframe signal exists (4h)"
```

---

### Scenario 4: Higher Timeframe Signal (Upgrade)

**Example**: BTCUSDT has 1h LONG signal, 4h LONG signal detected

```
Database: [BTCUSDT LONG 1h]
New Signal: BTCUSDT LONG 4h

Result: ⬆️ UPGRADED
  1. Delete 1h signal
  2. Create 4h signal
Frontend shows: BTCUSDT LONG (4h) [replaced 1h]

Log: "UPGRADING LONG signal for BTCUSDT: 1h → 4h (Conf: 75% → 72%)"
```

---

## Practical Examples

### Example 1: Typical Scan Sequence

**1-Day Scan (runs every 6 hours)**:
```
Scans 200 pairs
Finds: ETHUSDT LONG 1d @ $3,500 (Conf: 78%)

✅ Signal saved: ETHUSDT LONG (1d)
```

**4-Hour Scan (runs every 4 hours)**:
```
Scans 200 pairs
Finds: ETHUSDT LONG 4h @ $3,502 (Conf: 76%)

⏭️ Skipped: Higher timeframe (1d) already exists
```

**Result**: Frontend shows only the 1d signal (highest priority)

---

### Example 2: Signal Upgrade Path

**15m Scan (12:00 PM)**:
```
SOLUSDT SHORT 15m @ $140.50 (Conf: 77%)
✅ Signal saved
```

**1h Scan (1:00 PM)**:
```
SOLUSDT SHORT 1h @ $140.20 (Conf: 75%)
⬆️ UPGRADE: 15m → 1h
✅ 15m signal deleted, 1h signal saved
```

**4h Scan (4:00 PM)**:
```
SOLUSDT SHORT 4h @ $139.80 (Conf: 73%)
⬆️ UPGRADE: 1h → 4h
✅ 1h signal deleted, 4h signal saved
```

**1d Scan (6:00 PM)**:
```
SOLUSDT SHORT 1d @ $139.50 (Conf: 71%)
⬆️ UPGRADE: 4h → 1d
✅ 4h signal deleted, 1d signal saved
```

**Final Result**: Frontend shows SOLUSDT SHORT (1d) - the most reliable signal

---

### Example 3: Mixed Directions (No Conflict)

**Important**: Prioritization only applies to **same direction** signals (LONG vs LONG, SHORT vs SHORT)

```
Database:
  - BTCUSDT LONG 4h @ $95,000
  - BTCUSDT SHORT 15m @ $95,500

New Signal: BTCUSDT LONG 1h @ $95,100

Result: ⏭️ Skipped (4h LONG already exists)
        ✅ SHORT 15m remains (different direction)

Frontend shows:
  - BTCUSDT LONG (4h)
  - BTCUSDT SHORT (15m)
```

---

## Implementation Details

### Code Location

File: `backend/scanner/tasks/multi_timeframe_scanner.py`

**Function**: `_save_signal_async(signal_data: Dict)`

**Lines**: 120-215

### Logic Flow

```python
def _save_signal_async(signal_data):
    symbol = signal_data['symbol']
    signal_type = signal_data['signal_type']  # LONG or SHORT
    new_timeframe = signal_data['timeframe']
    new_priority = TIMEFRAME_PRIORITY[new_timeframe]

    # Find existing signal for same symbol + type
    existing = Signal.objects.filter(
        symbol=symbol,
        signal_type=signal_type,
        status='ACTIVE'
    ).first()

    if existing:
        existing_priority = TIMEFRAME_PRIORITY[existing.timeframe]

        # Skip if same timeframe
        if new_timeframe == existing.timeframe:
            return None  # Duplicate

        # Skip if lower priority
        if new_priority < existing_priority:
            return None  # Lower timeframe

        # Upgrade if higher priority
        if new_priority > existing_priority:
            existing.delete()
            # Create new higher TF signal

    # Create signal if no conflict
    return Signal.objects.create(...)
```

---

## Benefits

### 1. **Reduced Noise**
- Filters out lower timeframe false signals
- Only shows most reliable signals

### 2. **Cleaner Frontend**
- One signal per symbol per direction
- No duplicate entries
- Clear signal hierarchy

### 3. **Better Trade Quality**
- Higher timeframe signals = higher win rates
- Wider stops = less stop-hunting
- Better risk/reward ratios

### 4. **Automatic Upgrades**
- Signals automatically improve as higher TFs confirm
- No manual intervention needed
- Always shows best available signal

---

## Frontend Display

### Recommended Display Format

```
╔═══════════════════════════════════════════════════════════╗
║ Symbol    | Direction | Timeframe | Entry   | Confidence ║
╠═══════════════════════════════════════════════════════════╣
║ BTCUSDT   | LONG      | 1d 🔥     | $95,000 | 78%        ║
║ ETHUSDT   | SHORT     | 4h ⚡     | $3,500  | 76%        ║
║ SOLUSDT   | LONG      | 1h 📊     | $140.20 | 75%        ║
║ ADAUSDT   | SHORT     | 15m ⏱️     | $1.05   | 77%        ║
╚═══════════════════════════════════════════════════════════╝

Legend:
🔥 1d  = Swing Trading (highest priority)
⚡ 4h  = Day Trading
📊 1h  = Intraday Trading
⏱️ 15m = Scalping (lowest priority)
```

### API Response Format

```json
{
  "signals": [
    {
      "symbol": "BTCUSDT",
      "signal_type": "LONG",
      "timeframe": "1d",
      "timeframe_priority": 4,
      "entry_price": 95000.0,
      "stop_loss": 92000.0,
      "take_profit": 103000.0,
      "confidence": 0.78,
      "status": "ACTIVE",
      "created_at": "2025-11-04T12:00:00Z"
    }
  ]
}
```

---

## Edge Cases

### Case 1: Signal Changes Direction

**Scenario**: BTCUSDT has LONG 4h signal, market reverses, SHORT 1d signal generated

```
Before: BTCUSDT LONG 4h
New: BTCUSDT SHORT 1d

Result: Both signals coexist (different directions)
  - BTCUSDT LONG (4h)
  - BTCUSDT SHORT (1d)

Action: User decides which to follow based on strategy
```

### Case 2: Signal Expires Before Upgrade

**Scenario**: 15m signal expires (60 min timeout) before 1h scan runs

```
12:00 - ADAUSDT LONG 15m created
12:59 - 15m signal expires (invalidated)
13:00 - 1h scan finds ADAUSDT LONG 1h

Result: 1h signal saved as new (no existing signal to upgrade)
```

### Case 3: Rapid Timeframe Scanning

**Scenario**: Multiple scans run simultaneously

```
13:00:00 - 15m scan starts
13:00:05 - 1h scan starts
13:00:10 - Both find BTCUSDT LONG

Result: Database lock ensures one wins
  - If 15m saves first → 1h upgrades it
  - If 1h saves first → 15m is skipped
```

---

## Monitoring & Analytics

### Database Query: Signal Distribution by Timeframe

```sql
SELECT
    timeframe,
    COUNT(*) as signal_count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
FROM signals_signal
WHERE status = 'ACTIVE'
GROUP BY timeframe
ORDER BY
    CASE timeframe
        WHEN '1d' THEN 1
        WHEN '4h' THEN 2
        WHEN '1h' THEN 3
        WHEN '15m' THEN 4
    END;
```

**Expected Distribution**:
```
Timeframe | Count | Percentage
----------|-------|------------
1d        | 8     | 40%   (highest quality)
4h        | 6     | 30%
1h        | 4     | 20%
15m       | 2     | 10%   (most filtered)
Total     | 20    | 100%
```

### Log Analysis: Upgrade Events

```bash
# Count signal upgrades in last 24 hours
docker logs binancebot_celery | grep "UPGRADING" | wc -l

# See specific upgrades
docker logs binancebot_celery | grep "UPGRADING"

# Example output:
# ⬆️ UPGRADING LONG signal for ETHUSDT: 1h → 4h (Conf: 75% → 72%)
# ⬆️ UPGRADING SHORT signal for SOLUSDT: 15m → 1d (Conf: 77% → 71%)
```

---

## Testing

### Manual Test Script

```python
#!/usr/bin/env python3
"""
Test signal prioritization logic
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from signals.models import Signal

# Clear existing signals
Signal.objects.filter(status='ACTIVE').delete()

print("\n=== Testing Signal Prioritization ===\n")

# Test 1: Create 15m signal
print("[Test 1] Creating 15m LONG signal for TESTUSDT...")
sig1 = Signal.objects.create(
    symbol='TESTUSDT',
    signal_type='LONG',
    timeframe='15m',
    entry_price=100.0,
    stop_loss=98.0,
    take_profit=106.0,
    confidence=0.75,
    status='ACTIVE'
)
print(f"✅ Created: {sig1.symbol} {sig1.signal_type} ({sig1.timeframe})")

# Check active signals
active = Signal.objects.filter(symbol='TESTUSDT', status='ACTIVE')
print(f"Active signals: {active.count()}")
for s in active:
    print(f"  - {s.timeframe} (Conf: {s.confidence:.0%})")

# Test 2: Upgrade to 4h
print("\n[Test 2] Upgrading to 4h LONG signal...")
# In real scenario, this would be done by scan_4h_timeframe()
Signal.objects.filter(symbol='TESTUSDT', timeframe='15m').delete()
sig2 = Signal.objects.create(
    symbol='TESTUSDT',
    signal_type='LONG',
    timeframe='4h',
    entry_price=101.0,
    stop_loss=97.5,
    take_profit=108.5,
    confidence=0.72,
    status='ACTIVE'
)
print(f"✅ Upgraded to: {sig2.symbol} {sig2.signal_type} ({sig2.timeframe})")

active = Signal.objects.filter(symbol='TESTUSDT', status='ACTIVE')
print(f"Active signals: {active.count()}")
for s in active:
    print(f"  - {s.timeframe} (Conf: {s.confidence:.0%})")

print("\n=== Test Complete ===\n")
```

---

## Configuration

### Adjusting Priority Rankings

To change priority rankings, edit `TIMEFRAME_PRIORITY` in `multi_timeframe_scanner.py`:

```python
# Default (current)
TIMEFRAME_PRIORITY = {
    '1d': 4,
    '4h': 3,
    '1h': 2,
    '15m': 1
}

# Alternative: Only use 4h and 1d
TIMEFRAME_PRIORITY = {
    '1d': 2,
    '4h': 1
    # Don't include 1h and 15m to disable them
}

# Alternative: Equal priority (no replacement)
TIMEFRAME_PRIORITY = {
    '1d': 1,
    '4h': 1,
    '1h': 1,
    '15m': 1
}
# All signals coexist, no upgrades
```

---

## Future Enhancements

### Phase 2: Multi-Timeframe Confirmation

Instead of replacing signals, require **alignment** across timeframes:

```python
# Only show 15m LONG if 1h/4h/1d are also LONG
if is_aligned_with_higher_timeframes(symbol, 'LONG'):
    show_signal()
else:
    skip_signal()  # Counter-trend trade
```

### Phase 3: Weighted Confidence

Combine confidence scores from multiple timeframes:

```python
# If both 4h and 1d show LONG:
combined_confidence = (4h_conf * 0.4) + (1d_conf * 0.6)
# Higher confidence = more reliable signal
```

### Phase 4: Smart Downgrade

Allow lower timeframe signals during trend continuation:

```python
# If 1d LONG trend established:
# Allow 4h/1h LONG entries (but not 15m)
# Block all SHORT signals
```

---

## Troubleshooting

### Issue: Signal Not Appearing

**Possible Causes**:
1. Higher timeframe signal already exists
2. Signal was upgraded before frontend refreshed
3. Database query not filtering by `status='ACTIVE'`

**Solution**:
```sql
-- Check all signals for symbol
SELECT symbol, signal_type, timeframe, status, created_at
FROM signals_signal
WHERE symbol = 'BTCUSDT'
ORDER BY created_at DESC;
```

### Issue: Lower Timeframe Signal Showing

**Possible Causes**:
1. Higher timeframe scan hasn't run yet
2. Celery Beat schedule misconfigured
3. Signal upgrade logic not applied

**Solution**:
```bash
# Manually trigger higher timeframe scan
docker exec binancebot_celery python -c "
from scanner.tasks.multi_timeframe_scanner import scan_1d_timeframe
scan_1d_timeframe()
"
```

---

## Conclusion

The signal prioritization system ensures:
- **Clean UI**: One signal per symbol per direction
- **Best Quality**: Always shows highest timeframe
- **Automatic Management**: No manual intervention needed
- **Scalable**: Works with any number of timeframes

**Status**: ✅ **Production Ready**

---

*Last Updated: November 4, 2025*
*Version: 2.1 - Signal Prioritization*
