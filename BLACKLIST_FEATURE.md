# Symbol Blacklist Feature

## Overview

The Symbol Blacklist feature allows you to exclude specific trading symbols from:
- Signal generation (scanner will skip blacklisted symbols)
- Paper trading (system and user auto-trading)
- Real futures trading (critical safety feature)

This is useful for managing risk by excluding symbols that consistently lose money, are too volatile, have low liquidity, or are temporarily problematic.

## Features

### 1. Database Model
- **Symbol**: Trading pair (e.g., BTCUSDT, DOGEUSDT)
- **Reason**: Categorized reason for blacklisting
  - HIGH_VOLATILITY - Too risky
  - LOW_LIQUIDITY - Poor fills
  - POOR_PERFORMANCE - Consistent losses
  - DELISTED - No longer available
  - TEMPORARY - Short-term exclusion
  - MANUAL - User preference
  - OTHER
- **Notes**: Detailed explanation
- **Blacklist Duration**:
  - Permanent (no expiration date)
  - Temporary (auto-removes after specified date)
- **Active Status**: Enable/disable without deleting

### 2. Django Admin Interface

**Access**: `http://localhost:8000/admin/signals/blacklistedsymbol/`

**Features**:
- Color-coded reason badges
- Active/Inactive/Expired status badges
- Bulk actions:
  - Activate selected blacklists
  - Deactivate selected blacklists
  - Make permanent (remove expiration)
- Filtering by:
  - Active status
  - Reason
  - Blacklist date
- Search by symbol or notes

**Screenshots of Admin Features**:
- Reason badges: RED (High Volatility), ORANGE (Poor Performance), YELLOW (Low Liquidity), etc.
- Status badges: RED (Active), GREEN (Inactive), GRAY (Expired)

### 3. REST API Endpoints

All endpoints are prefixed with `/api/blacklist/`

#### List Blacklisted Symbols
```bash
GET /api/blacklist/
```

**Query Parameters**:
- `active` (boolean): Filter by active status
- `reason` (string): Filter by reason
- `symbol` (string): Search by symbol name
- `include_expired` (boolean): Include/exclude expired entries (default: true)

**Response**:
```json
[
  {
    "id": 1,
    "symbol": "DOGEUSDT",
    "reason": "POOR_PERFORMANCE",
    "reason_display": "Poor Performance - Consistent losses",
    "notes": "Consistent losses, too volatile for current strategy",
    "blacklisted_at": "2025-12-13T10:34:47.041293Z",
    "blacklisted_until": null,
    "is_expired": false,
    "active": true,
    "created_at": "2025-12-13T10:34:47.041293Z",
    "updated_at": "2025-12-13T10:34:47.041293Z"
  }
]
```

#### Check if Symbols are Blacklisted (Public)
```bash
POST /api/blacklist/check/
Content-Type: application/json

{
  "symbols": ["BTCUSDT", "DOGEUSDT", "ETHUSDT"]
}
```

**Response**:
```json
{
  "BTCUSDT": {
    "blacklisted": false
  },
  "DOGEUSDT": {
    "blacklisted": true,
    "reason": "POOR_PERFORMANCE",
    "reason_display": "Poor Performance - Consistent losses",
    "notes": "Consistent losses, too volatile for current strategy",
    "blacklisted_at": "2025-12-13T10:34:47.041293Z",
    "blacklisted_until": null
  },
  "ETHUSDT": {
    "blacklisted": false
  }
}
```

#### Get Active Blacklisted Symbols (Public)
```bash
GET /api/blacklist/active/
```

**Response**:
```json
{
  "blacklisted_symbols": ["DOGEUSDT", "SHIBUSDT"],
  "count": 2
}
```

#### Create Blacklist Entry (Requires Auth)
```bash
POST /api/blacklist/
Authorization: Token YOUR_TOKEN
Content-Type: application/json

{
  "symbol": "SHIBUSDT",
  "reason": "HIGH_VOLATILITY",
  "notes": "Too much price swing causing stop loss hits",
  "blacklisted_until": "2025-12-20T00:00:00Z"  // Optional
}
```

**Response**:
```json
{
  "id": 2,
  "symbol": "SHIBUSDT",
  "reason": "HIGH_VOLATILITY",
  "reason_display": "High Volatility - Too risky",
  "notes": "Too much price swing causing stop loss hits",
  "blacklisted_at": "2025-12-13T10:45:00Z",
  "blacklisted_until": "2025-12-20T00:00:00Z",
  "is_expired": false,
  "active": true,
  "created_at": "2025-12-13T10:45:00Z",
  "updated_at": "2025-12-13T10:45:00Z"
}
```

#### Update Blacklist Entry (Requires Auth)
```bash
PATCH /api/blacklist/{id}/
Authorization: Token YOUR_TOKEN
Content-Type: application/json

{
  "active": false,
  "notes": "Re-enabled after strategy adjustment"
}
```

#### Delete Blacklist Entry (Requires Auth)
```bash
DELETE /api/blacklist/{id}/
Authorization: Token YOUR_TOKEN
```

#### Activate/Deactivate Blacklist Entry (Requires Auth)
```bash
POST /api/blacklist/{id}/activate/
POST /api/blacklist/{id}/deactivate/
```

#### Extend Blacklist Duration (Requires Auth)
```bash
POST /api/blacklist/{id}/extend/
Content-Type: application/json

{
  "days": 7  // Extend by 7 days
}
```

#### Make Blacklist Permanent (Requires Auth)
```bash
POST /api/blacklist/{id}/make_permanent/
```

Removes expiration date, making the blacklist entry permanent.

### 4. Integration Points

#### Signal Generation Scanner
**File**: `backend/scanner/tasks/celery_tasks.py`

**How it works**:
1. Scanner fetches all active blacklisted symbols at the start of each scan
2. Skips processing blacklisted symbols entirely
3. Logs which symbols are being skipped

**Log Output**:
```
📛 Skipping 2 blacklisted symbols: ['DOGEUSDT', 'SHIBUSDT']
⏭️  Skipping blacklisted symbol: DOGEUSDT
```

#### Paper Trading (System-wide)
**File**: `backend/signals/signals_handlers.py`

**Handler**: `create_system_paper_trade()`

**How it works**:
1. When a new signal is created, checks if symbol is blacklisted
2. If blacklisted, logs and skips creating paper trade
3. System paper trades are public and visible on dashboard

**Log Output**:
```
📛 Signal 123 (DOGEUSDT) is blacklisted, skipping system paper trade
```

#### Paper Trading (User Auto-trading)
**File**: `backend/signals/signals_handlers.py`

**Handler**: `auto_execute_trade_on_signal()`

**How it works**:
1. When user has auto-trading enabled, checks if symbol is blacklisted
2. If blacklisted, skips executing auto-trade for that user
3. Protects user accounts from trading blacklisted symbols

**Log Output**:
```
📛 Signal 123 (DOGEUSDT) is blacklisted, skipping auto-trade
```

#### Real Futures Trading (Critical Safety)
**File**: `backend/signals/signals_handlers.py`

**Handler**: `execute_futures_trade_on_signal()`

**How it works**:
1. **BLOCKS** real money futures trades on blacklisted symbols
2. Uses `logger.warning()` for high visibility
3. Critical safety feature to prevent trading problematic symbols with real money

**Log Output**:
```
🚫 Signal 123 (DOGEUSDT) is blacklisted, BLOCKING real futures trade for safety!
```

## Usage Examples

### Example 1: Blacklist a Volatile Coin
```bash
# Add DOGEUSDT to blacklist due to high volatility
curl -X POST http://localhost:8000/api/blacklist/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "DOGEUSDT",
    "reason": "HIGH_VOLATILITY",
    "notes": "Price swings too large, causing SL hits"
  }'
```

### Example 2: Temporary Blacklist (1 Week)
```bash
# Blacklist ETHUSDT for 7 days due to upcoming event
curl -X POST http://localhost:8000/api/blacklist/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETHUSDT",
    "reason": "TEMPORARY",
    "notes": "ETH 2.0 upgrade causing volatility",
    "blacklisted_until": "2025-12-20T00:00:00Z"
  }'
```

### Example 3: Check Blacklist Before Trading
```bash
# Check if symbols are blacklisted
curl -X POST http://localhost:8000/api/blacklist/check/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTCUSDT", "DOGEUSDT", "ETHUSDT"]
  }'
```

### Example 4: Get All Active Blacklisted Symbols
```bash
# Get current blacklist
curl http://localhost:8000/api/blacklist/active/

# Response: {"blacklisted_symbols": ["DOGEUSDT"], "count": 1}
```

### Example 5: Deactivate Blacklist Entry
```bash
# Remove DOGEUSDT from blacklist
curl -X POST http://localhost:8000/api/blacklist/1/deactivate/ \
  -H "Authorization: Token YOUR_TOKEN"
```

## Database Schema

```sql
CREATE TABLE signals_blacklisted_symbols (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    reason VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    notes TEXT,
    blacklisted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    blacklisted_until TIMESTAMP WITH TIME ZONE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_blacklisted_symbol_active
    ON signals_blacklisted_symbols(symbol, active);

CREATE INDEX idx_blacklisted_active_date
    ON signals_blacklisted_symbols(active, blacklisted_at);
```

## Model Methods

### Class Methods
```python
# Check if a symbol is blacklisted
BlacklistedSymbol.is_blacklisted('BTCUSDT')  # Returns: True/False

# Get all currently blacklisted symbols
BlacklistedSymbol.get_blacklisted_symbols()  # Returns: ['DOGEUSDT', 'SHIBUSDT']
```

### Instance Methods
```python
# Check if entry has expired
entry.is_expired()  # Returns: True/False

# Auto-deactivate on save if expired
entry.save()  # Automatically sets active=False if blacklisted_until has passed
```

## Performance Considerations

1. **Caching**: Blacklist is fetched once per scanner run and reused
2. **Indexes**: Database indexes on `(symbol, active)` and `(active, blacklisted_at)` for fast lookups
3. **Minimal Overhead**: Check is a simple list membership test: `if symbol in blacklisted_symbols`

## Testing

Run the test suite:
```bash
docker exec binancebot_web python manage.py test signals.tests.test_blacklist
```

### Manual Testing Checklist

- [ ] Add blacklist entry via admin
- [ ] Check entry appears in `/api/blacklist/active/`
- [ ] Run scanner and verify blacklisted symbols are skipped
- [ ] Create a signal for blacklisted symbol manually
- [ ] Verify paper trade is NOT created
- [ ] Deactivate blacklist entry
- [ ] Verify symbol is now processed normally
- [ ] Test temporary blacklist expiration
- [ ] Test bulk actions in admin

## Security Considerations

1. **API Authentication**: Most endpoints require authentication (except `/check/` and `/active/` for public access)
2. **Real Futures Protection**: Blacklist check in `execute_futures_trade_on_signal()` prevents real money trades
3. **Input Validation**: Symbol names are uppercased and validated
4. **Unique Constraint**: Prevents duplicate blacklist entries for same symbol

## Future Enhancements

Potential improvements:
1. **Auto-blacklist**: Automatically blacklist symbols with N consecutive losses
2. **Whitelist Mode**: Only trade whitelisted symbols
3. **Performance-based Blacklist**: Auto-blacklist based on win rate/ROI thresholds
4. **Symbol Groups**: Blacklist entire categories (e.g., all meme coins)
5. **Frontend UI**: React component for managing blacklist

## Troubleshooting

### Symbol still being traded after blacklisting
1. Check if entry is active: `SELECT * FROM signals_blacklisted_symbols WHERE symbol='DOGEUSDT';`
2. Restart Celery worker: `docker restart binancebot_celery`
3. Check logs: `docker logs binancebot_celery --tail 100 | grep blacklist`

### API returns "Authentication required"
Use public endpoints (`/check/` and `/active/`) or provide valid auth token

### Blacklist not appearing in admin
1. Run migrations: `docker exec binancebot_web python manage.py migrate`
2. Restart Django: `docker restart binancebot_web`

## Files Modified/Created

### Created Files:
- `backend/signals/models_blacklist.py` - BlacklistedSymbol model
- `backend/signals/serializers_blacklist.py` - API serializers
- `backend/signals/views_blacklist.py` - API viewset
- `BLACKLIST_FEATURE.md` - This documentation

### Modified Files:
- `backend/signals/models.py` - Import BlacklistedSymbol
- `backend/signals/admin.py` - BlacklistedSymbolAdmin
- `backend/api/urls.py` - Register blacklist routes
- `backend/scanner/tasks/celery_tasks.py` - Skip blacklisted symbols in scanner
- `backend/signals/signals_handlers.py` - Skip blacklisted symbols in all trading handlers

## Conclusion

The Symbol Blacklist feature provides comprehensive control over which symbols are traded by the bot. It integrates seamlessly with all trading operations (signal generation, paper trading, real futures trading) and provides both API and admin interfaces for management.

**Key Safety Feature**: Blacklist prevents real money futures trades on problematic symbols, protecting your capital.
