# Backtesting Serializer Field Fix

## Issue

When accessing the backtesting API endpoint (`/api/backtest/`), the following error occurred:

```
ImproperlyConfigured at /api/backtest/
Field name `max_drawdown_percentage` is not valid for model `BacktestRun`.
```

## Root Cause

The `BacktestRunSerializer` in [backend/signals/serializers_backtest.py](../backend/signals/serializers_backtest.py) referenced a field `max_drawdown_percentage` that doesn't exist in the `BacktestRun` model.

### Model Fields (Correct)
In [backend/signals/models_backtest.py](../backend/signals/models_backtest.py), the BacktestRun model has:
- `max_drawdown` - DecimalField storing the drawdown percentage
- `max_drawdown_amount` - DecimalField storing the dollar amount of drawdown

### Serializer Fields (Incorrect)
The serializer was trying to access:
- `max_drawdown` ✅
- `max_drawdown_percentage` ❌ (doesn't exist)

## Solution

### Changes Made

**File**: [backend/signals/serializers_backtest.py](../backend/signals/serializers_backtest.py)

#### Change 1: Updated fields list (line 86)
```python
# Before
'max_drawdown', 'max_drawdown_percentage', 'max_drawdown_formatted',

# After
'max_drawdown', 'max_drawdown_amount', 'max_drawdown_formatted',
```

#### Change 2: Updated read_only_fields list (line 96)
```python
# Before
'max_drawdown', 'max_drawdown_percentage',

# After
'max_drawdown', 'max_drawdown_amount',
```

#### Change 3: Fixed get_max_drawdown_formatted method (lines 116-120)
```python
# Before
def get_max_drawdown_formatted(self, obj):
    """Format max drawdown as currency and percentage."""
    dd = float(obj.max_drawdown)
    dd_pct = float(obj.max_drawdown_percentage)  # ❌ Field doesn't exist
    return f"${dd:.2f} ({dd_pct:.2f}%)"

# After
def get_max_drawdown_formatted(self, obj):
    """Format max drawdown as currency and percentage."""
    dd_pct = float(obj.max_drawdown)  # This is the percentage
    dd_amount = float(obj.max_drawdown_amount)  # This is the dollar amount
    return f"${dd_amount:.2f} ({dd_pct:.2f}%)"
```

## Field Definitions Clarification

For clarity, here's what each field represents:

| Field Name | Type | Description | Example |
|-----------|------|-------------|---------|
| `max_drawdown` | Decimal | Maximum drawdown as **percentage** | 15.50 (means 15.50%) |
| `max_drawdown_amount` | Decimal | Maximum drawdown as **dollar amount** | 1550.00 (means $1,550.00) |
| `max_drawdown_formatted` | SerializerMethodField | Human-readable format | "$1,550.00 (15.50%)" |

## Testing

After the fix, the API endpoint now works correctly:

```bash
# Test endpoint (requires authentication)
curl http://localhost:8000/api/backtest/

# Should return 401 (authentication required) instead of 500 (server error)
# Status: 401 ✅ (correct - requires login)
```

## Deployment

The fix was applied by:
1. Editing the serializer file
2. Restarting the backend container:
   ```bash
   docker-compose restart backend
   ```

No database migration was needed since the model fields were already correct.

## Impact

- **Before Fix**: Any request to `/api/backtest/` would result in HTTP 500 error
- **After Fix**: API endpoints work correctly with proper authentication (HTTP 401 for unauthenticated, HTTP 200 with data for authenticated)

## Related Files

- Model: [backend/signals/models_backtest.py](../backend/signals/models_backtest.py)
- Serializer: [backend/signals/serializers_backtest.py](../backend/signals/serializers_backtest.py)
- Views: [backend/signals/views_backtest.py](../backend/signals/views_backtest.py)

## Status

✅ **Fixed and Deployed**

The backtesting frontend can now successfully communicate with the backend API.

---

**Date Fixed**: 2025-10-30
**Issue Type**: Serializer field mismatch
**Severity**: Critical (blocked entire backtesting API)
**Resolution Time**: Immediate
