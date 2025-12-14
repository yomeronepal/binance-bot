# Automatic Coin Blacklisting Feature

## Overview

The bot now automatically detects and handles coins that are causing API errors (typically 400 Bad Request from Binance), which usually indicates the coin has been delisted or is no longer available for trading.

## What It Does

When the bot encounters a coin that fails price fetching with a 400 error, it will automatically:

1. **Blacklist the coin** - Adds the symbol to the `BlacklistedSymbol` database table with:
   - Reason: `DELISTED`
   - Notes: Error message from Binance API
   - Active: `true`

2. **Close associated paper trades** - Any open paper trades for that symbol are closed:
   - Status: `CLOSED_MANUAL`
   - Exit price: Entry price (no profit/loss)
   - P/L: $0.00 (0%)

3. **Prevent future trades** - The blacklisted symbol is excluded from:
   - Signal generation
   - Paper trading
   - Auto-trading

## Implementation Details

### Modified Files

**`backend/signals/views_public_paper_trading.py`**:
- Added `handle_failing_symbol()` function (lines 22-60)
- Updated `public_performance()` to detect and handle failing symbols (lines 221-247)
- Updated `public_open_positions()` to detect and handle failing symbols (lines 306-334)
- Updated `public_close_trade()` to handle failing symbols (lines 461-489)

### How It Works

When fetching live prices from Binance:

```python
async def fetch_prices():
    prices = {}
    failed_symbols = {}
    for symbol in symbols:
        try:
            price_data = await binance_client.get_price(symbol)
            if price_data and 'price' in price_data:
                prices[symbol] = Decimal(str(price_data['price']))
        except Exception as e:
            error_msg = str(e)
            # Check if it's a 400 error (likely delisted coin)
            if '400' in error_msg or 'Bad Request' in error_msg:
                failed_symbols[symbol] = error_msg
                logger.error(f"❌ Request failed: {error_msg}")
    return prices, failed_symbols
```

Then handle failed symbols:

```python
# Handle failed symbols - blacklist and close trades
for symbol, error_msg in failed_symbols.items():
    failing_trades = open_trades_queryset.filter(symbol=symbol)
    for trade in failing_trades:
        handle_failing_symbol(symbol, error_msg, trade)
```

### Database Schema

The blacklist uses the existing `BlacklistedSymbol` model:

```python
class BlacklistedSymbol(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    notes = models.TextField(blank=True, null=True)
    blacklisted_at = models.DateTimeField(default=timezone.now)
    blacklisted_until = models.DateTimeField(blank=True, null=True)  # Optional expiry
    active = models.BooleanField(default=True)
```

## Example Scenario

### Before Auto-Blacklist

```
2025-12-14 10:53:00,480 ERROR ❌ Request failed: ClientResponseError: 400,
  message='Bad Request', url=URL('https://api.binance.com/api/v3/ticker/price?symbol=BSVUSDT')
2025-12-14 10:53:05,123 ERROR ❌ Request failed: ClientResponseError: 400,
  message='Bad Request', url=URL('https://api.binance.com/api/v3/ticker/price?symbol=BSVUSDT')
(Error repeats every time bot checks prices...)
```

### After Auto-Blacklist

```
2025-12-14 10:53:00,480 ERROR ❌ Request failed: ClientResponseError: 400,
  message='Bad Request', url=URL('https://api.binance.com/api/v3/ticker/price?symbol=BSVUSDT')
2025-12-14 10:53:00,485 WARNING 🚫 Auto-blacklisted BSVUSDT due to API error:
  ClientResponseError: 400, message='Bad Request'
2025-12-14 10:53:00,490 INFO ✅ Closed failing trade 123 for BSVUSDT at entry price
2025-12-14 10:53:05,123 INFO ⏭️ BSVUSDT already blacklisted, skipping
(No more errors - symbol is blacklisted)
```

## Benefits

1. **Prevents system errors** - Stops repeated failed API requests
2. **Clean logs** - Reduces error spam in logs
3. **Accurate reporting** - Closed trades don't show as "stuck open"
4. **No manual intervention** - Fully automated
5. **Future protection** - Blacklisted coins won't be traded again

## Monitoring

### View Blacklisted Symbols

**Via API**:
```bash
# Get all active blacklisted symbols
curl http://localhost:8000/api/blacklist/active/

# Get full blacklist with details
curl http://localhost:8000/api/blacklist/?active=true
```

**Via Django Admin**:
1. Navigate to http://localhost:8000/admin/
2. Click "Blacklisted Symbols"
3. Filter by active=true

**Via Database**:
```sql
SELECT symbol, reason, notes, blacklisted_at
FROM signals_blacklisted_symbols
WHERE active = true
ORDER BY blacklisted_at DESC;
```

### Logs to Watch

Look for these log messages:

- `❌ Request failed:` - API error detected
- `🚫 Auto-blacklisted` - Symbol added to blacklist
- `✅ Closed failing trade` - Trade closed successfully
- `⏭️ {symbol} already blacklisted` - Duplicate detection prevented

## Manual Management

### Add Symbol to Blacklist

```bash
curl -X POST http://localhost:8000/api/blacklist/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbol": "LUNAUSDT",
    "reason": "DELISTED",
    "notes": "Manually blacklisted - high risk",
    "active": true
  }'
```

### Remove from Blacklist

```bash
curl -X DELETE http://localhost:8000/api/blacklist/{id}/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Or deactivate temporarily:

```bash
curl -X POST http://localhost:8000/api/blacklist/{id}/deactivate/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Known Auto-Blacklisted Symbols

As of 2025-12-14:
- **BSVUSDT** - 400 Bad Request (likely delisted)

## Configuration

### Disable Auto-Blacklist (Not Recommended)

If you need to disable this feature temporarily, comment out the error handling in:
- `backend/signals/views_public_paper_trading.py` (lines 327-334, 242-247, 483-489)

### Adjust Error Detection

Currently detects:
- 400 status codes
- "Bad Request" in error message

To add more error types, modify the condition:
```python
if '400' in error_msg or 'Bad Request' in error_msg or 'Symbol not found' in error_msg:
```

## Testing

### Test Auto-Blacklist

1. Create a paper trade for a delisted coin (if possible)
2. Wait for price fetching to fail
3. Check logs for auto-blacklist messages
4. Verify trade is closed
5. Verify symbol is in blacklist

### Verify Blacklist Works

```bash
# Check if symbol is blacklisted
curl -X POST http://localhost:8000/api/blacklist/check/ \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["BSVUSDT", "BTCUSDT"]}'

# Response:
{
  "BSVUSDT": {
    "blacklisted": true,
    "reason": "DELISTED",
    "notes": "Auto-blacklisted: ClientResponseError...",
    "blacklisted_at": "2025-12-14T10:53:00Z"
  },
  "BTCUSDT": {
    "blacklisted": false
  }
}
```

## Future Enhancements

Potential improvements:
1. **Auto-expire blacklist** - Set `blacklisted_until` for temporary issues
2. **Retry logic** - Try multiple times before blacklisting
3. **Email notifications** - Alert admins when coins are auto-blacklisted
4. **Analytics** - Track most commonly failing symbols
5. **Whitelist override** - Allow specific symbols to bypass blacklist

## Related Files

- `backend/signals/models_blacklist.py` - Blacklist database model
- `backend/signals/views_blacklist.py` - Blacklist API endpoints
- `backend/signals/serializers_blacklist.py` - Blacklist serializers
- `backend/scanner/tasks/celery_tasks.py` - Uses blacklist in signal generation
- `docs/BLACKLIST_FEATURE.md` - Original blacklist documentation

## Support

If you encounter issues:
1. Check Docker logs: `docker logs binancebot_web`
2. Check database: `SELECT * FROM signals_blacklisted_symbols;`
3. Verify API endpoints work
4. Check scanner logs for blacklist filtering

---

**Status**: ✅ Active (Deployed 2025-12-14)
**Impact**: Prevents system errors from delisted/unavailable coins
**Automation**: Fully automatic - no manual intervention required
