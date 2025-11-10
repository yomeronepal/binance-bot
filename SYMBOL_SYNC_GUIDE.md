# Symbol Sync & Scan Guide

Complete guide for syncing all Binance symbols and scanning them for signals.

---

## Overview

The `sync_and_scan_all` management command fetches all USDT trading pairs from Binance, saves them to the database using upsert (update or insert), and optionally scans them for trading signals.

### Features

✅ **Bulk Upsert** - Efficiently updates existing symbols or creates new ones
✅ **Volume Sorting** - Fetches 24h volume data and sorts symbols by liquidity
✅ **Signal Scanning** - Scans all symbols for trading opportunities
✅ **Flexible Options** - Fetch-only, scan-only, or both
✅ **Progress Tracking** - Real-time progress updates and statistics
✅ **Error Handling** - Continues on errors, reports issues

---

## Quick Start

### Sync All Symbols (Fetch + Scan)

```bash
# Local development
docker exec binancebot_web python manage.py sync_and_scan_all

# Production server (via SSH)
ssh root@YOUR_SERVER_IP
cd /root/binance-bot
docker compose -f docker-compose.prod.yml exec web python manage.py sync_and_scan_all
```

### Fetch Only (No Scanning)

```bash
# Just update the symbol database
docker exec binancebot_web python manage.py sync_and_scan_all --fetch-only
```

### Scan Only (Existing Symbols)

```bash
# Scan symbols already in database
docker exec binancebot_web python manage.py sync_and_scan_all --scan-only
```

---

## Command Options

### `--fetch-only`

Only fetch and save symbols from Binance, skip signal scanning.

**Use case**: Initial setup, periodic symbol list updates

```bash
python manage.py sync_and_scan_all --fetch-only
```

**Output**:
- ✅ Fetches all USDT pairs from Binance
- ✅ Gets 24h volume data for sorting
- ✅ Saves/updates symbols in database
- ❌ Does NOT scan for signals

---

### `--scan-only`

Only scan existing symbols in database, skip fetching from Binance.

**Use case**: Re-scan after strategy changes, manual signal generation

```bash
python manage.py sync_and_scan_all --scan-only
```

**Output**:
- ❌ Does NOT fetch new symbols
- ✅ Loads active symbols from database
- ✅ Scans all symbols for signals
- ✅ Generates new trading signals

---

### `--limit N`

Limit the number of symbols to scan (for testing).

**Use case**: Testing new strategies, quick validation

```bash
# Only scan top 50 symbols
python manage.py sync_and_scan_all --limit 50
```

**Output**:
- ✅ Fetches all symbols (if not --scan-only)
- ✅ Scans only first N symbols
- ⚠️  Useful for testing, not production

---

### `--interval TIMEFRAME`

Specify timeframe for scanning (default: 1h).

**Use case**: Different timeframe analysis

```bash
# Scan on 4-hour timeframe
python manage.py sync_and_scan_all --interval 4h

# Scan on 15-minute timeframe
python manage.py sync_and_scan_all --interval 15m
```

**Supported intervals**: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w

---

## Usage Examples

### Example 1: Initial Setup

```bash
# First deployment - fetch all symbols
docker compose -f docker-compose.prod.yml exec web python manage.py sync_and_scan_all --fetch-only
```

**What happens**:
1. Connects to Binance API
2. Fetches all ~400-500 USDT pairs
3. Gets volume data for each pair
4. Sorts by 24h volume (highest first)
5. Saves to database with upsert
6. Shows statistics

**Expected output**:
```
======================================================================
🚀 Binance Symbol Sync & Scanner
======================================================================
──────────────────────────────────────────────────────────────────────
📡 STEP 1: Fetching Symbols from Binance
──────────────────────────────────────────────────────────────────────
🔌 Checking Binance API connectivity...
✅ Connected to Binance API

📊 Fetching all USDT trading pairs...
✅ Fetched 463 USDT pairs from Binance

💹 Fetching volume data for sorting...
  Batch 1/10: Fetching 50 symbols...
  Batch 2/10: Fetching 50 symbols...
  ...
✅ Sorted 463 symbols by volume

💾 Saving symbols to database...
    ✅ Created: BTCUSDT
    ✅ Created: ETHUSDT
    ✅ Created: BNBUSDT
    ...
    ... and 453 more

📊 Database Update:
  ├─ New symbols: 463
  ├─ Updated symbols: 0
  ├─ Total symbols: 463
  └─ Database total: 463

======================================================================
✅ Operation Complete!
======================================================================
```

---

### Example 2: Full Sync + Scan

```bash
# Fetch symbols AND scan for signals
docker compose -f docker-compose.prod.yml exec web python manage.py sync_and_scan_all
```

**What happens**:
1. Fetches and saves all symbols (as above)
2. Fetches 200 candles for each symbol
3. Calculates technical indicators
4. Scans for LONG/SHORT signals
5. Saves signals to database
6. Shows found signals

**Expected output**:
```
======================================================================
🚀 Binance Symbol Sync & Scanner
======================================================================
[... symbol fetch output ...]

──────────────────────────────────────────────────────────────────────
🔍 STEP 2: Scanning Symbols for Signals
──────────────────────────────────────────────────────────────────────

📊 Scanning 463 symbols on 1h timeframe...

📈 Fetching candlestick data...
  Batch 1/93: Fetching 5 symbols...
  ✅ Batch 1/93 complete: 5 succeeded, 0 failed (2.3s)
  ...
✅ Fetched data for 458/463 symbols

  🆕 [12/458] SOLUSDT: LONG signal at $143.25 (Confidence: 75%)
  🆕 [45/458] AVAXUSDT: SHORT signal at $32.18 (Confidence: 82%)
  📊 Progress: 50/458 symbols processed, 2 signals found
  🆕 [89/458] MATICUSDT: LONG signal at $0.85 (Confidence: 73%)
  📊 Progress: 100/458 symbols processed, 3 signals found
  ...

📊 Scan Results:
  ├─ Symbols processed: 458
  ├─ Signals found: 8
  └─ Success rate: 99.1%

======================================================================
✅ Operation Complete!
======================================================================
```

---

### Example 3: Test Strategy Changes

```bash
# Test on 50 symbols first
docker exec binancebot_web python manage.py sync_and_scan_all --scan-only --limit 50
```

**Use case**: You modified the signal engine and want to test it quickly.

---

### Example 4: Re-scan After Parameter Update

```bash
# Scan existing symbols with new parameters
docker exec binancebot_web python manage.py sync_and_scan_all --scan-only --interval 4h
```

**Use case**: You updated `MIN_CONFIDENCE` or other strategy parameters.

---

## Automated Sync

### On Every Deployment

The deployment workflow automatically syncs symbols after deploying:

```yaml
# .github/workflows/deploy.yml
echo "==> Syncing all Binance symbols..."
docker compose -f docker-compose.prod.yml exec -T web python manage.py sync_and_scan_all --fetch-only
```

**When it runs**:
- Automatically after `docker compose up -d`
- Only fetches symbols (no scanning)
- Continues deployment even if it fails

---

### Manual GitHub Action

Trigger manual sync + scan from GitHub:

1. Go to: `https://github.com/YOUR_USERNAME/binance-bot/actions`
2. Click: `Fetch All Binance Symbols`
3. Click: `Run workflow`
4. Select: `main` branch
5. Click: `Run workflow` button

**What it does**:
- SSHs into your server
- Runs `sync_and_scan_all` (full sync + scan)
- Shows symbol and signal counts
- Reports completion status

---

## Performance

### Timing Estimates

| Operation | Symbols | Time |
|-----------|---------|------|
| Fetch symbols | ~460 | 30-60 seconds |
| Fetch volume data | ~460 | 2-3 minutes |
| Save to database | ~460 | 5-10 seconds |
| Scan symbols (1h) | ~460 | 5-8 minutes |
| **Total (fetch + scan)** | ~460 | **8-12 minutes** |

### Rate Limiting

The command respects Binance API rate limits:

- **Volume fetch**: 50 symbols/batch, 0.5s delay between batches
- **Kline fetch**: 5 symbols/batch, 1.5s delay between batches
- **Internal rate limiter**: Max 800 requests/minute

---

## Database Operations

### Upsert Logic

The command uses `update_or_create` for efficient upserts:

```python
Symbol.objects.update_or_create(
    symbol=symbol,
    defaults={
        'exchange': 'BINANCE',
        'active': True
    }
)
```

**Behavior**:
- If symbol exists: Updates `exchange` and `active` fields
- If symbol doesn't exist: Creates new record
- Uses database transaction for atomicity

---

## Troubleshooting

### Issue: "Cannot connect to Binance API"

**Cause**: Network connectivity or VPN blocking Binance

**Solution**:
```bash
# Test connectivity
curl https://api.binance.com/api/v3/ping

# If blocked, configure VPN or use proxy
```

---

### Issue: "Connection timeout" during scan

**Cause**: Server has slow internet or is rate limited

**Solution**:
```bash
# Reduce batch size and increase delays
# Edit: backend/scanner/services/binance_client.py
# Line 372: batch_size=5 -> batch_size=3
# Line 373: delay_between_batches=1.5 -> delay_between_batches=2.0
```

---

### Issue: Fewer symbols than expected

**Cause**: Some symbols failed to fetch due to API errors

**Solution**: The command continues on errors. Check logs:
```bash
# View detailed logs
docker compose -f docker-compose.prod.yml logs web | grep "Error"

# Re-run to fetch missing symbols
docker compose -f docker-compose.prod.yml exec web python manage.py sync_and_scan_all --fetch-only
```

---

### Issue: No signals found

**Possible causes**:
1. Market conditions (no setups matching criteria)
2. Confidence threshold too high
3. Strategy parameters too strict

**Solution**:
```bash
# Check active signals
docker exec binancebot_web python manage.py shell -c "
from signals.models import Signal
print(f'Active signals: {Signal.objects.filter(status=\"ACTIVE\").count()}')
"

# Lower confidence in .env and re-scan
MIN_CONFIDENCE=0.60
docker exec binancebot_web python manage.py sync_and_scan_all --scan-only
```

---

## Monitoring

### Check Symbol Count

```bash
docker exec binancebot_web python manage.py shell -c "
from signals.models import Symbol
print(f'Total: {Symbol.objects.count()}')
print(f'Active: {Symbol.objects.filter(active=True).count()}')
print(f'Binance: {Symbol.objects.filter(exchange=\"BINANCE\").count()}')
"
```

### Check Signal Count

```bash
docker exec binancebot_web python manage.py shell -c "
from signals.models import Signal
from django.utils import timezone
from datetime import timedelta

active = Signal.objects.filter(status='ACTIVE').count()
today = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(days=1)).count()

print(f'Active signals: {active}')
print(f'Created today: {today}')
"
```

---

## Integration with Celery

The scanner runs automatically via Celery Beat every hour:

```python
# backend/config/celery.py
app.conf.beat_schedule = {
    'scan-binance-market': {
        'task': 'scanner.tasks.scan_binance_market',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

**Manual command vs Celery**:
- **Manual**: Full control, immediate execution, on-demand
- **Celery**: Automatic, scheduled, background execution

---

## Summary

**Quick Commands**:
```bash
# Full sync (fetch + scan)
python manage.py sync_and_scan_all

# Fetch only
python manage.py sync_and_scan_all --fetch-only

# Scan only
python manage.py sync_and_scan_all --scan-only

# Test with 50 symbols
python manage.py sync_and_scan_all --limit 50

# Different timeframe
python manage.py sync_and_scan_all --interval 4h
```

**GitHub Actions**:
- Automatic sync on deployment (fetch-only)
- Manual sync via `Fetch All Binance Symbols` workflow

**Performance**:
- ~460 symbols fetched in 2-3 minutes
- Full scan takes 8-12 minutes
- Respects API rate limits

---

**Last Updated**: 2025-11-11
**Status**: ✅ Production Ready
