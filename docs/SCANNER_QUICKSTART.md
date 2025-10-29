# Binance Scanner - Quick Start Guide

Get the Binance signal scanner up and running in 5 minutes!

## Prerequisites

- Python 3.11+
- Redis server running
- PostgreSQL database configured
- Django project set up

## Step 1: Install Dependencies

```bash
cd backend
pip install aiohttp==3.9.1 pandas==2.1.4 numpy==1.26.2
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Step 2: Configure Environment

Add to your `.env` file:

```bash
# Binance Scanner Settings
BINANCE_INTERVAL=5m
POLLING_INTERVAL=60
BINANCE_BATCH_SIZE=20
TOP_PAIRS=50
MIN_CONFIDENCE=0.7
```

## Step 3: Run Database Migrations

```bash
python manage.py migrate
```

## Step 4: Start Redis (if not running)

```bash
# Linux/Mac
redis-server

# Windows (with WSL)
wsl redis-server

# Or Docker
docker run -d -p 6379:6379 redis:7-alpine
```

## Step 5: Start Django with Channels Support

In one terminal:

```bash
python manage.py runserver
```

Or with Daphne (recommended for WebSocket):

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

## Step 6: Start the Scanner

In another terminal:

```bash
python manage.py run_scanner
```

You should see output like:

```
Starting Binance Scanner...
Configuration:
  Interval: 5m
  Poll Interval: 60s
  Min Confidence: 0.7
  Batch Size: 20
  Top Pairs: 50

Starting Binance polling worker (interval=5m, min_confidence=0.7)
Found 2847 USDT pairs
Selected top 50 pairs by 24h volume
Top 3 pairs by volume: BTCUSDT ($45.2B), ETHUSDT ($18.3B), SOLUSDT ($5.1B)
Starting polling cycle at 12:00:00
Fetched klines for 50/50 symbols
🚀 LONG signal for BTCUSDT: Entry=$42500.50, Confidence=85.0%
🚀 SHORT signal for ETHUSDT: Entry=$2250.75, Confidence=78.5%
✅ Cycle completed in 8.45s. Signals: 2, Errors: 0
Polling cycle completed. Sleeping for 60s
```

## Step 7: Test WebSocket Connection

Open your frontend at `http://localhost:5174` and check the browser console for:

```
WebSocket connected - subscribing to signals
New signal: {symbol: 'BTCUSDT', direction: 'LONG', ...}
```

## Verify It's Working

### Check Database

```bash
python manage.py shell
```

```python
from signals.models import Signal
Signal.objects.count()  # Should show generated signals
Signal.objects.filter(status='ACTIVE').order_by('-created_at')[:5]
```

### Check Logs

Scanner logs will show:
- ✅ Successful polling cycles
- 🚀 Generated signals
- ⚠️ Warnings (if any)
- ❌ Errors (if any)

## Common Issues & Solutions

### Issue: "Channel layer not configured"

**Solution**: Ensure Redis is running and `CHANNEL_LAYERS` is configured in settings.py:

```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

### Issue: "Rate limit reached"

**Solution**: Binance hit rate limit. Reduce `BATCH_SIZE` or increase `POLLING_INTERVAL`:

```bash
python manage.py run_scanner --batch-size 10 --poll-interval 120
```

### Issue: No signals generated

**Solutions**:
1. Lower confidence threshold: `--min-confidence 0.6`
2. Check market conditions (low volatility = fewer signals)
3. Monitor more pairs: `--top-pairs 100`

### Issue: Import errors

**Solution**: Make sure you're in the backend directory and Django settings are configured:

```bash
export DJANGO_SETTINGS_MODULE=config.settings
cd backend
python manage.py run_scanner
```

## Custom Configuration

### Different Timeframe

```bash
python manage.py run_scanner --interval 15m --poll-interval 300
```

### More Aggressive Signals

```bash
python manage.py run_scanner --min-confidence 0.5 --top-pairs 100
```

### Conservative Signals

```bash
python manage.py run_scanner --min-confidence 0.85 --top-pairs 20
```

## Monitoring

### Watch Live Signals

```bash
python manage.py shell
```

```python
from signals.models import Signal
import time

while True:
    latest = Signal.objects.order_by('-created_at').first()
    if latest:
        print(f"{latest.created_at}: {latest.direction} {latest.symbol} @ ${latest.entry} (Conf: {latest.confidence:.0%})")
    time.sleep(5)
```

### Check System Stats

```python
from signals.models import Signal, Symbol
from django.utils import timezone
from datetime import timedelta

# Signals in last hour
one_hour_ago = timezone.now() - timedelta(hours=1)
recent_signals = Signal.objects.filter(created_at__gte=one_hour_ago)
print(f"Signals in last hour: {recent_signals.count()}")

# By direction
longs = recent_signals.filter(direction='LONG').count()
shorts = recent_signals.filter(direction='SHORT').count()
print(f"LONG: {longs}, SHORT: {shorts}")

# Average confidence
avg_conf = recent_signals.aggregate(models.Avg('confidence'))
print(f"Average confidence: {avg_conf['confidence__avg']:.2%}")
```

## Production Deployment

### Use Supervisor

Create `/etc/supervisor/conf.d/scanner.conf`:

```ini
[program:binance_scanner]
command=/path/to/venv/bin/python /path/to/backend/manage.py run_scanner
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/scanner.log
```

### Use Systemd

Create `/etc/systemd/system/scanner.service`:

```ini
[Unit]
Description=Binance Scanner Service
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/venv/bin/python manage.py run_scanner
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable scanner
sudo systemctl start scanner
sudo systemctl status scanner
```

## Next Steps

1. **Monitor Performance**: Check CPU, memory, and network usage
2. **Tune Parameters**: Adjust confidence threshold based on signal quality
3. **Analyze Results**: Track which signals lead to profitable trades
4. **Scale Up**: Add more pairs or reduce polling interval
5. **Enhance Strategy**: Modify signal generation logic in `signal_generator.py`

## Getting Help

- Check logs: `tail -f /var/log/scanner.log`
- Django logs: Check `DEBUG=True` in settings
- Open GitHub issue with logs and configuration

## Performance Benchmarks

On a typical VPS (2 CPU, 4GB RAM):

- **50 pairs**: ~8-12 seconds per cycle
- **100 pairs**: ~15-20 seconds per cycle
- **Memory**: ~150MB
- **Signals per hour**: 2-10 (varies by market conditions)

Enjoy trading! 🚀
