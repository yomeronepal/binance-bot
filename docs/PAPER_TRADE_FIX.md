# Paper Trade Creation Fix

## Issue
When clicking "Create Paper Trade" button on the dashboard, the following error occurred:
```
Failed to create paper trade: Failed to create trade
```

## Root Cause
The `PaperTradingService.create_paper_trade()` method was trying to access `signal.symbol_name` attribute which doesn't exist in the Signal model.

**Error in backend logs:**
```
'Signal' object has no attribute 'symbol_name'
```

**Location:** `backend/signals/services/paper_trader.py:54`

## Signal Model Structure
The Signal model has a ForeignKey relationship to the Symbol model:
```python
class Signal(models.Model):
    symbol = models.ForeignKey('Symbol', on_delete=models.CASCADE)
    # ... other fields
```

To get the symbol string, we need to access: `signal.symbol.symbol`

## Fix Applied

**File:** `backend/signals/services/paper_trader.py`

**Before (Line 54):**
```python
symbol=signal.symbol_name or signal.symbol.symbol,
```

**After (Lines 50-60):**
```python
# Get symbol string - handle both ForeignKey and string cases
if hasattr(signal.symbol, 'symbol'):
    symbol_str = signal.symbol.symbol
else:
    symbol_str = str(signal.symbol)

# Create paper trade
paper_trade = PaperTrade.objects.create(
    signal=signal,
    user=user,
    symbol=symbol_str,  # Using the correctly extracted symbol string
    # ... rest of fields
)
```

## Solution
Added proper handling to extract the symbol string from the Signal model's ForeignKey relationship:

1. Check if `signal.symbol` has a `symbol` attribute (ForeignKey case)
2. If yes, use `signal.symbol.symbol` to get the string
3. If no, convert `signal.symbol` to string directly (fallback)

This makes the code more robust and handles different scenarios.

## Testing

### API Test (Success):
```bash
$ curl -X POST http://localhost:8000/api/paper-trades/create_from_signal/ \
  -H "Content-Type: application/json" \
  -d '{"signal_id": 1, "position_size": 100}'

# Response:
{
  "id": 1,
  "symbol": "USDCUSDT",
  "direction": "SHORT",
  "entry_price": "0.99970000",
  "position_size": "100.00000000",
  "quantity": "100.03000900",
  "stop_loss": "0.99991429",
  "take_profit": "0.99934286",
  "status": "OPEN",
  ...
}
```

### Verify Trade Created:
```bash
$ curl http://localhost:8000/api/paper-trades/

# Response:
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "symbol": "USDCUSDT",
      "status": "OPEN",
      ...
    }
  ]
}
```

### Check Performance Metrics:
```bash
$ curl http://localhost:8000/api/paper-trades/performance/

# Response:
{
  "total_trades": 0,
  "open_trades": 1,
  "win_rate": 0,
  ...
}
```

## Frontend Usage

Now users can successfully create paper trades:

1. **Go to Dashboard:** http://localhost:5173/dashboard
2. **Ensure Paper Trading mode is selected** (purple toggle)
3. **Click "📝 Create Paper Trade"** on any ACTIVE signal
4. **Success!** Alert shows: "Paper trade created successfully!"
5. **View trade:** Navigate to http://localhost:5173/paper-trading

## Services Restarted
```bash
docker-compose restart backend celery-worker
```

## Status
✅ **FIXED** - Paper trade creation now works correctly

## Date
October 29, 2025
