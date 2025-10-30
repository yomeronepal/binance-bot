# Strategy Dashboard - Data Loading Guide

**Created**: October 30, 2025
**Purpose**: Load and refresh strategy performance data for the dashboard

---

## Overview

The Strategy Dashboard displays aggregated performance analytics from completed backtests. This guide shows you how to load data into the dashboard using both manual and automated methods.

---

## Quick Start

### Option 1: Manual Loading (Recommended First Time)

```bash
# Load data immediately
docker-compose exec backend python manage.py load_strategy_dashboard

# Clear cache and reload
docker-compose exec backend python manage.py load_strategy_dashboard --clear-cache

# Load specific time range
docker-compose exec backend python manage.py load_strategy_dashboard --time-range 30d

# Run as async task
docker-compose exec backend python manage.py load_strategy_dashboard --async
```

### Option 2: Automatic Loading (Celery Beat)

Celery beat automatically runs these tasks:
- **Every hour (at :05)**: Aggregate all strategy performance data
- **Every 30 minutes**: Check for stale cache and refresh if needed

```bash
# Verify celery-beat is running
docker-compose ps celery-beat

# Check celery-beat logs
docker-compose logs celery-beat --tail 50

# Trigger manual aggregation via Celery
docker-compose exec backend python -c "
from signals.tasks_strategy_performance import aggregate_strategy_performance
result = aggregate_strategy_performance.delay()
print(f'Task ID: {result.id}')
"
```

---

## Data Loading Methods

### Method 1: Django Management Command

**Best for**: Initial setup, manual refreshes, testing

```bash
# Basic usage
docker-compose exec backend python manage.py load_strategy_dashboard
```

**Options**:
- `--clear-cache`: Delete existing cache before loading
- `--time-range <range>`: Load specific range (7d, 30d, 90d, all)
- `--async`: Run as background Celery task

**Examples**:

```bash
# Load all data with fresh cache
docker-compose exec backend python manage.py load_strategy_dashboard --clear-cache

# Load only last 30 days
docker-compose exec backend python manage.py load_strategy_dashboard --time-range 30d

# Async load (non-blocking)
docker-compose exec backend python manage.py load_strategy_dashboard --async
```

### Method 2: Celery Tasks

**Best for**: Automated refreshes, scheduled updates

#### Available Tasks:

1. **aggregate_strategy_performance**
   - Aggregates data for all time ranges (7d, 30d, 90d, all)
   - Caches results for 1 hour
   - Runs automatically every hour

2. **check_stale_cache**
   - Checks if cache is expired
   - Triggers refresh if needed
   - Runs every 30 minutes

3. **refresh_strategy_dashboard**
   - Force refresh specific time range
   - Invalidates cache first

4. **invalidate_strategy_cache**
   - Clears all cached data
   - Useful after major changes

#### Manual Trigger:

```bash
# In Django shell
docker-compose exec backend python manage.py shell

from signals.tasks_strategy_performance import *

# Aggregate all data
result = aggregate_strategy_performance.delay()
print(f"Task started: {result.id}")

# Check task status
result.ready()  # True if complete
result.get()    # Get result (blocks until done)

# Refresh specific range
refresh_strategy_dashboard.delay('30d')

# Invalidate cache
invalidate_strategy_cache.delay()
```

### Method 3: API Endpoint

**Best for**: On-demand refresh from frontend

```bash
# Get data (uses cache if available)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/strategy/performance/?time_range=30d

# Force refresh (bypass cache)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/strategy/performance/?time_range=30d&force_refresh=true
```

---

## Celery Beat Schedule

Current schedule in `config/celery.py`:

```python
'aggregate-strategy-performance': {
    'task': 'signals.aggregate_strategy_performance',
    'schedule': crontab(minute=5),  # Every hour at :05
},

'check-stale-cache': {
    'task': 'signals.check_stale_cache',
    'schedule': crontab(minute='*/30'),  # Every 30 minutes
},
```

**What this means**:
- Data aggregates at 00:05, 01:05, 02:05, etc.
- Cache checks at 00:00, 00:30, 01:00, 01:30, etc.
- Fresh data available within 5 minutes of any hour

---

## Data Flow

```
┌─────────────────┐
│ Backtest        │
│ Completes       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Wait for next   │
│ hourly trigger  │ ←─ Celery Beat (hourly)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Aggregate Task  │
│ Runs            │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Calculate:      │
│ - By volatility │
│ - By symbol     │
│ - By config     │
│ - Sharpe ratio  │
│ - Heatmap       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Cache Results   │
│ (1 hour TTL)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ API serves data │
│ from cache      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Dashboard       │
│ displays charts │
└─────────────────┘
```

---

## Cache Behavior

### Cache Keys:
- `strategy_performance_7d`
- `strategy_performance_30d`
- `strategy_performance_90d`
- `strategy_performance_all`

### Cache Lifetime:
- **TTL**: 1 hour (3600 seconds)
- **Auto-refresh**: Every hour via Celery beat
- **Manual refresh**: Use `?force_refresh=true` parameter

### Cache Data Structure:
```json
{
  "byVolatility": [...],
  "bySymbol": [...],
  "configurations": [...],
  "sharpeOverTime": [...],
  "heatmap": [...],
  "mlOptimization": null,
  "last_updated": "2025-10-30T15:30:00Z",
  "backtest_count": 5
}
```

---

## Prerequisites

### Required: Completed Backtests

The dashboard needs completed backtests to display data.

**Check if you have data**:
```bash
docker-compose exec backend python manage.py shell

from signals.models_backtest import BacktestRun
completed = BacktestRun.objects.filter(status='COMPLETED').count()
print(f"Completed backtests: {completed}")
```

**If you have 0 backtests**, run some first:
```bash
# Option 1: Use the local backtest script
python backtest_strategy.py

# Option 2: Via API
curl -X POST http://localhost:8000/api/backtest/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Backtest",
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "timeframe": "5m",
    "start_date": "2024-12-01",
    "end_date": "2024-12-31"
  }'
```

---

## Troubleshooting

### Problem: Dashboard shows "No data available"

**Solution 1**: Check if you have completed backtests
```bash
docker-compose exec backend python manage.py shell
>>> from signals.models_backtest import BacktestRun
>>> BacktestRun.objects.filter(status='COMPLETED').count()
```

**Solution 2**: Manually load data
```bash
docker-compose exec backend python manage.py load_strategy_dashboard --clear-cache
```

**Solution 3**: Check cache
```bash
docker-compose exec backend python manage.py shell
>>> from django.core.cache import cache
>>> cache.get('strategy_performance_30d')
```

### Problem: Data is stale/old

**Solution**: Force refresh
```bash
# Via management command
docker-compose exec backend python manage.py load_strategy_dashboard --clear-cache

# Via API
curl "http://localhost:8000/api/strategy/performance/?time_range=30d&force_refresh=true" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Problem: Celery beat not running tasks

**Check 1**: Verify celery-beat is running
```bash
docker-compose ps celery-beat
# Should show "Up"
```

**Check 2**: Check logs
```bash
docker-compose logs celery-beat --tail 100 | grep "aggregate-strategy"
```

**Check 3**: Restart celery-beat
```bash
docker-compose restart celery-beat
```

### Problem: Task failing with errors

**Check logs**:
```bash
# Backend logs
docker-compose logs backend --tail 100 | grep "strategy"

# Celery worker logs
docker-compose logs celery-worker --tail 100 | grep "aggregate_strategy"

# Celery beat logs
docker-compose logs celery-beat --tail 50
```

---

## Performance Considerations

### Data Volume Impact

| Backtests | Aggregation Time | Cache Size |
|-----------|------------------|------------|
| 1-10 | <1 second | ~50 KB |
| 10-50 | 1-3 seconds | ~200 KB |
| 50-100 | 3-5 seconds | ~500 KB |
| 100+ | 5-10 seconds | ~1 MB |

### Optimization Tips

1. **Use cache**: Don't force refresh unless necessary
2. **Limit time range**: Use 30d instead of 'all' for faster load
3. **Run async**: Use `--async` flag for large datasets
4. **Schedule wisely**: Default hourly refresh is usually sufficient

---

## Testing

### Test 1: Manual Load
```bash
docker-compose exec backend python manage.py load_strategy_dashboard
# Should see: ✅ Aggregation complete
```

### Test 2: API Access
```bash
# Login to get token
TOKEN=$(curl -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | jq -r '.access')

# Get performance data
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/strategy/performance/?time_range=30d" \
  | jq .
```

### Test 3: Celery Task
```bash
docker-compose exec backend python manage.py shell
>>> from signals.tasks_strategy_performance import aggregate_strategy_performance
>>> result = aggregate_strategy_performance()
>>> print(result)
{'status': 'success', 'time_ranges_processed': [...]}
```

---

## Best Practices

### Initial Setup
1. Run several backtests first
2. Manually load data: `load_strategy_dashboard --clear-cache`
3. Verify in dashboard
4. Let Celery beat handle updates

### Regular Operation
1. Celery beat auto-refreshes hourly
2. Cache serves fast responses
3. Force refresh only when needed
4. Monitor Celery logs for errors

### After Major Changes
1. Clear cache: `--clear-cache`
2. Reload data: `load_strategy_dashboard`
3. Verify in dashboard
4. Check logs for errors

---

## Summary

### Loading Data - Quick Reference

```bash
# First time setup
docker-compose exec backend python manage.py load_strategy_dashboard --clear-cache

# Manual refresh
docker-compose exec backend python manage.py load_strategy_dashboard

# Async refresh
docker-compose exec backend python manage.py load_strategy_dashboard --async

# Force refresh via API
curl "http://localhost:8000/api/strategy/performance/?force_refresh=true" \
  -H "Authorization: Bearer TOKEN"

# Check Celery beat
docker-compose logs celery-beat --tail 20
```

### Automatic Updates

✅ **Celery beat handles it automatically**
- Aggregates data every hour at :05
- Checks cache every 30 minutes
- No manual intervention needed

---

**Next**: Open http://localhost:3000/strategy-dashboard to view your analytics!

