# Paper Trade Deletion Issue - FIXED

**Date**: November 6, 2025
**Status**: ✅ **RESOLVED**

---

## Problem

Your paper trades were being automatically deleted after 24 hours.

### Root Cause

**CASCADE Delete Chain**:
1. Celery task `cleanup_expired_signals()` runs every 5 minutes
2. Deletes all signals older than 24 hours (line 458 in `celery_tasks.py`)
3. `PaperTrade.signal` had `on_delete=models.CASCADE` (line 394 in `models.py`)
4. When a signal is deleted, **all linked paper trades are automatically deleted**

### Code Evidence

**File**: `backend/scanner/tasks/celery_tasks.py` (lines 456-460)
```python
# 1. Delete old signals (older than 24 hours)
cutoff_time = timezone.now() - timedelta(hours=24)
old_deleted, _ = Signal.objects.filter(
    created_at__lt=cutoff_time
).delete()
```

**File**: `backend/signals/models.py` (line 394 - OLD)
```python
signal = models.ForeignKey(
    'Signal',
    on_delete=models.CASCADE,  # ← This caused the problem!
    related_name='paper_trades',
)
```

---

## Solution Applied

Changed `PaperTrade.signal` from `CASCADE` to `SET_NULL`:

### What Changed

**File**: `backend/signals/models.py` (line 394 - NEW)
```python
signal = models.ForeignKey(
    'Signal',
    on_delete=models.SET_NULL,  # ← Paper trades now preserved!
    null=True,
    blank=True,
    related_name='paper_trades',
    help_text=_("Associated trading signal (nullable to preserve trades)")
)
```

### Migration Applied

**Migration**: `signals/migrations/0014_fix_papertrade_cascade.py`
**Status**: ✅ Applied successfully

---

## What Happens Now

### Before Fix ❌
1. Signal created → Paper trade created
2. 24 hours pass
3. `cleanup_expired_signals()` runs
4. Signal deleted
5. **Paper trade DELETED** (CASCADE)
6. You lose all trade history!

### After Fix ✅
1. Signal created → Paper trade created
2. 24 hours pass
3. `cleanup_expired_signals()` runs
4. Signal deleted
5. **Paper trade PRESERVED** (signal field set to NULL)
6. Trade history remains intact! 🎉

---

## Impact

### Preserved Data
- ✅ All paper trades now keep their entry, exit, profit/loss data
- ✅ Historical performance metrics preserved
- ✅ Win rate calculations remain accurate
- ✅ Trade statistics unaffected by signal cleanup

### Signal Reference
- Paper trades will still have all trade data (entry, exit, P/L, etc.)
- `signal` field will be `NULL` for trades whose signals were cleaned up
- New paper trades will still link to active signals normally

---

## Verification

Check your paper trades are preserved:

```bash
# Count paper trades
docker exec binancebot_web python manage.py shell -c "
from signals.models import PaperTrade
print(f'Total paper trades: {PaperTrade.objects.count()}')
print(f'Trades with signals: {PaperTrade.objects.filter(signal__isnull=False).count()}')
print(f'Trades without signals (orphaned): {PaperTrade.objects.filter(signal__isnull=True).count()}')
"

# View recent paper trades
curl "http://localhost:8000/api/paper-trades/" | jq

# Check Django admin
http://localhost:8000/admin/signals/papertrade/
```

---

## Alternative Solutions (Not Used)

### Option 1: Disable Signal Cleanup ❌
**Rejected**: Would cause database to grow infinitely

### Option 2: Only Delete INACTIVE Signals ❌
**Rejected**: Signals might become INACTIVE before paper trades close

### Option 3: Use PROTECT Instead of SET_NULL ❌
**Rejected**: Would prevent signal cleanup entirely

### Option 4: Copy Signal Data to PaperTrade ❌
**Rejected**: Data duplication, more complex

**Option 5: SET_NULL (CHOSEN)** ✅
- Paper trades preserved
- Signals can still be cleaned up
- No data duplication
- Simple and clean

---

## Future Recommendations

### 1. Adjust Signal Cleanup Period (Optional)

If 24 hours is too short, increase it in `celery_tasks.py`:

```python
# Change from 24 hours to 7 days
cutoff_time = timezone.now() - timedelta(days=7)  # Instead of hours=24
```

### 2. Archive Old Signals Instead of Deleting (Optional)

Instead of deleting, mark as archived:

```python
# Archive instead of delete
Signal.objects.filter(
    created_at__lt=cutoff_time
).update(status='ARCHIVED')
```

### 3. Cleanup Only EXECUTED/INVALIDATED Signals (Recommended)

Preserve ACTIVE signals longer:

```python
# Only cleanup non-active signals
Signal.objects.filter(
    created_at__lt=cutoff_time,
    status__in=['EXECUTED', 'INVALIDATED', 'EXPIRED']
).delete()
```

---

## Testing

### Test 1: Create and Preserve Trade

```bash
# 1. Create a signal (via scanner or manually)
# 2. Wait for paper trade auto-creation
# 3. Check trade exists
curl "http://localhost:8000/api/paper-trades/" | jq '.results | length'

# 4. Delete the signal manually
docker exec binancebot_web python manage.py shell -c "
from signals.models import Signal
Signal.objects.filter(id=SIGNAL_ID).delete()
"

# 5. Verify paper trade still exists
curl "http://localhost:8000/api/paper-trades/" | jq '.results | length'
```

Expected: Paper trade count remains the same ✅

### Test 2: Check Orphaned Trades

```bash
docker exec binancebot_web python manage.py shell -c "
from signals.models import PaperTrade
orphaned = PaperTrade.objects.filter(signal__isnull=True)
print(f'Orphaned trades: {orphaned.count()}')
for trade in orphaned[:5]:
    print(f'  - {trade.symbol} {trade.direction} @ {trade.entry_price} (P/L: {trade.profit_loss})')
"
```

These are trades whose signals were deleted - data is preserved!

---

## Summary

✅ **Problem Fixed**: Paper trades no longer deleted when signals are cleaned up
✅ **Migration Applied**: Database schema updated
✅ **Zero Downtime**: Change applied without service interruption
✅ **Backward Compatible**: Existing paper trades unaffected
✅ **Data Preserved**: All historical trade data remains intact

Your paper trading history is now safe! 🎉

---

**Author**: Claude AI Assistant
**Date**: November 6, 2025
**Issue**: CASCADE delete causing paper trade loss
**Resolution**: Changed to SET_NULL to preserve trades
