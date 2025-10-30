# Strategy Performance Import Fix

**Date**: October 30, 2025
**Issue**: ImportError in strategy performance views
**Status**: ✅ Fixed

---

## Problem

Backend failed to start with the following error:

```
ImportError: cannot import name 'Backtest' from 'scanner.models'
ImportError: cannot import name 'Backtest' from 'signals.models'
```

**Root Cause**: Incorrect model import in `signals/views_strategy_performance.py`

---

## Solution

### File Modified
`backend/signals/views_strategy_performance.py`

### Changes Made

**Before (Incorrect)**:
```python
from scanner.models import Backtest, BacktestTrade
```

**After (Correct)**:
```python
from signals.models_backtest import BacktestRun, BacktestTrade
```

**Also Updated References**:
- `Backtest.objects` → `BacktestRun.objects`

---

## Model Location

The backtest models are located in:
- **File**: `backend/signals/models_backtest.py`
- **Models**:
  - `BacktestRun` - Main backtest run model
  - `BacktestTrade` - Individual trade in backtest
  - `BacktestMetric` - Performance metrics

---

## Verification

```bash
# Restart backend
docker-compose restart backend

# Check logs
docker-compose logs backend --tail 20

# Expected output:
# "Starting server at tcp:port=8000"
# "Listening on TCP address 0.0.0.0:8000"
```

---

## Testing

Access the strategy performance API:
```bash
# Should return 401 (needs auth) instead of 500 (import error)
curl http://localhost:8000/api/strategy/performance/
```

---

## Status

✅ **Fixed** - Backend starting successfully
✅ **Import Error Resolved**
✅ **API Endpoint Available**

---

**Last Updated**: October 30, 2025
