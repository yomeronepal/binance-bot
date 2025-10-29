# Celery Integration Guide - Binance Bot

## 🎯 Overview

Celery is integrated for asynchronous task execution and periodic scheduling. This enables background processing of market data, signal notifications, and system maintenance without blocking the main Django application.

### Key Features

- ✅ **Periodic Market Scanning** - Every 60 seconds
- ✅ **Automatic Signal Refresh** - Hourly data refresh
- ✅ **High-Priority Notifications** - Every 2 minutes for high-confidence signals
- ✅ **Automatic Cleanup** - Every 5 minutes removes old signals
- ✅ **Health Monitoring** - Every 10 minutes checks system status
- ✅ **Task Retry Logic** - Exponential backoff on failures
- ✅ **Queue Routing** - Separate queues for different task types
- ✅ **Flower Dashboard** - Real-time task monitoring

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Django Application                    │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │   Redis Broker       │
        │   (Port 6379)        │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────────────────────────────────┐
        │              Celery Workers                      │
        │  ┌──────────────────────────────────────────┐  │
        │  │  Queue: scanner (concurrency: 2)         │  │
        │  │  - scan_binance_market                   │  │
        │  └──────────────────────────────────────────┘  │
        │  ┌──────────────────────────────────────────┐  │
        │  │  Queue: notifications (concurrency: 4)   │  │
        │  │  - send_signal_notifications             │  │
        │  └──────────────────────────────────────────┘  │
        │  ┌──────────────────────────────────────────┐  │
        │  │  Queue: maintenance (concurrency: 1)     │  │
        │  │  - full_data_refresh                     │  │
        │  │  - cleanup_expired_signals               │  │
        │  │  - system_health_check                   │  │
        │  └──────────────────────────────────────────┘  │
        └──────────────┬──────────────────────────────────┘
                       │
        ┌──────────────▼──────────┐
        │     Celery Beat          │
        │  (Periodic Scheduler)    │
        └──────────────┬──────────┘
                       │
        ┌──────────────▼──────────┐
        │  Django DB (Beat Store) │
        └──────────────────────────┘
```

---

## 📦 Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- `celery==5.3.4` - Task queue framework
- `redis==5.0.1` - Message broker and result backend
- `django-celery-beat==2.5.0` - Database-backed periodic scheduler
- `django-celery-results==2.5.1` - Task result storage in Django DB
- `flower==2.0.1` - Web-based monitoring tool

### 2. Apply Migrations

```bash
python manage.py migrate
```

This creates tables for:
- `django_celery_beat` - Periodic task schedules
- `django_celery_results` - Task execution results

---

## 🚀 Running Celery

### Development Setup

You need to run **three separate processes**:

#### Terminal 1: Celery Worker

```bash
cd backend
celery -A config worker -l info -Q scanner,notifications,maintenance
```

Options:
- `-A config` - Application module
- `-l info` - Log level (debug, info, warning, error, critical)
- `-Q` - Queues to consume from

**For Windows:**
```bash
celery -A config worker -l info -Q scanner,notifications,maintenance --pool=solo
```

#### Terminal 2: Celery Beat Scheduler

```bash
cd backend
celery -A config beat -l info
```

This reads the schedule from Django database and triggers periodic tasks.

#### Terminal 3: Flower Monitoring (Optional)

```bash
cd backend
celery -A config flower --port=5555
```

Access Flower dashboard at: http://localhost:5555

---

## 🔧 Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Binance Scanner Settings
BINANCE_INTERVAL=5m
POLLING_INTERVAL=60
MIN_CONFIDENCE=0.7
TOP_PAIRS=50

# Binance API (Optional - for authenticated endpoints)
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

### Task Configuration

Edit `backend/config/celery.py` to customize:

```python
app.conf.beat_schedule = {
    'scan-binance-market': {
        'task': 'scanner.tasks.celery_tasks.scan_binance_market',
        'schedule': 60.0,  # Change interval (seconds)
    },
    # ... other tasks
}
```

---

## 📋 Periodic Tasks

### 1. Market Scanner (`scan_binance_market`)

**Schedule:** Every 60 seconds
**Queue:** `scanner`
**Retries:** 3 (exponential backoff)

Fetches candle data for top 50 USDT pairs, calculates indicators, and generates/updates/removes signals.

**Logs:**
```
🔄 Starting Binance market scan...
✅ Market scan completed: Created=2, Updated=5, Deleted=1, Active=15
```

**Customization:**
```python
# In celery_tasks.py
config = SignalConfig(
    min_confidence=0.75,  # Higher threshold
    long_rsi_min=55.0,
    sl_atr_multiplier=2.0
)
```

### 2. Full Data Refresh (`full_data_refresh`)

**Schedule:** Every hour (on the hour)
**Queue:** `maintenance`
**Retries:** 2

Marks signals older than 1 hour as EXPIRED.

**Logs:**
```
🔄 Starting full data refresh...
📊 Full refresh: Marked 12 signals as expired
```

### 3. Signal Notifications (`send_signal_notifications`)

**Schedule:** Every 2 minutes
**Queue:** `notifications`
**Retries:** 3

Broadcasts high-confidence signals (≥85%) via WebSocket.

**Logs:**
```
📬 Checking for signal notifications...
📨 Notification sent: LONG BTCUSDT (Conf: 88%)
✅ Sent 3 notifications
```

### 4. Cleanup Expired Signals (`cleanup_expired_signals`)

**Schedule:** Every 5 minutes
**Queue:** `maintenance`
**Retries:** None (fire-and-forget)

Deletes signals older than 24 hours from database.

**Logs:**
```
🧹 Cleaning up expired signals...
✅ Cleaned up 47 old signals
```

### 5. System Health Check (`system_health_check`)

**Schedule:** Every 10 minutes
**Queue:** `maintenance`
**Retries:** None

Monitors database, Redis, and counts active signals.

**Logs:**
```
🏥 Running system health check...
✅ Health check passed: {'database': 'connected', 'active_signals': 15, 'redis': 'connected'}
```

---

## 🧪 Testing Tasks

### Manual Task Execution

Test individual tasks from Django shell:

```python
python manage.py shell
```

```python
from scanner.tasks.celery_tasks import *

# Test simple task
result = test_celery_task.delay("Hello from Celery!")
print(result.get())  # Wait for result

# Test market scan
task = scan_binance_market.delay()
print(task.state)  # PENDING, STARTED, SUCCESS, FAILURE

# Check task result
result = task.get(timeout=120)  # Wait up to 2 minutes
print(result)
# {'created': 2, 'updated': 3, 'deleted': 1, 'active': 15}

# Test cleanup
cleanup_expired_signals.delay()

# Check health
health = system_health_check.delay()
print(health.get())
```

### Run Unit Tests

```bash
cd backend
pytest scanner/tests/test_celery_tasks.py -v
```

Expected output:
```
test_scan_success PASSED
test_scan_retry_on_error PASSED
test_refresh_expires_old_signals PASSED
test_sends_high_confidence_signals PASSED
test_deletes_old_signals PASSED
test_health_check_success PASSED
... 20 tests passed
```

---

## 📊 Monitoring with Flower

### Starting Flower

```bash
celery -A config flower --port=5555
```

### Dashboard Features

**Access:** http://localhost:5555

1. **Tasks** - View all tasks (pending, active, completed, failed)
2. **Workers** - Monitor worker status, queues, concurrency
3. **Broker** - Redis connection status
4. **Stats** - Task throughput, success/failure rates
5. **Monitor** - Real-time task execution

### Key Metrics

- **Task Success Rate** - Should be >95%
- **Average Task Duration** - `scan_binance_market` ~10-15s
- **Active Workers** - Should match your worker count
- **Queue Lengths** - Should be close to 0 (no backlog)

---

## 🔍 Troubleshooting

### Issue 1: Celery worker not starting

**Error:**
```
ModuleNotFoundError: No module named 'config'
```

**Fix:**
```bash
# Make sure you're in the backend directory
cd backend
celery -A config worker -l info
```

### Issue 2: Tasks not executing

**Check:**
1. Is Redis running?
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

2. Is Celery Beat running?
   ```bash
   ps aux | grep celery
   ```

3. Check task routes:
   ```python
   # In Django shell
   from config.celery import app
   print(app.conf.task_routes)
   ```

### Issue 3: "Connection refused" errors

**Fix:**
```bash
# Check Redis is running
redis-cli ping

# Check Redis URL in .env matches
echo $REDIS_URL

# Restart Redis
# Linux/Mac:
redis-server

# Docker:
docker-compose up redis
```

### Issue 4: Tasks timing out

**Increase timeout:**
```python
# In config/celery.py
app.conf.update(
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 minutes soft limit
)
```

### Issue 5: High memory usage

**Solution:**
```bash
# Reduce worker concurrency
celery -A config worker -l info --concurrency=2

# Or use prefork pool with autoscaling
celery -A config worker -l info --autoscale=10,3
```

---

## 🛠️ Production Deployment

### Using Supervisor (Linux)

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A config worker -l info -Q scanner,notifications,maintenance
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/celery/worker.err.log
stdout_logfile=/var/log/celery/worker.out.log

[program:celery-beat]
command=/path/to/venv/bin/celery -A config beat -l info
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/celery/beat.err.log
stdout_logfile=/var/log/celery/beat.out.log
```

Start services:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery-worker celery-beat
```

### Using Systemd (Linux)

Create `/etc/systemd/system/celery.service`:

```ini
[Unit]
Description=Celery Service
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A config worker -l info -Q scanner,notifications,maintenance --detach

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery
sudo systemctl start celery
```

### Using Docker

Add to `docker-compose.yml`:

```yaml
services:
  celery-worker:
    build: ./backend
    command: celery -A config worker -l info -Q scanner,notifications,maintenance
    volumes:
      - ./backend:/app
    env_file:
      - ./backend/.env
    depends_on:
      - redis
      - postgres

  celery-beat:
    build: ./backend
    command: celery -A config beat -l info
    volumes:
      - ./backend:/app
    env_file:
      - ./backend/.env
    depends_on:
      - redis
      - postgres

  flower:
    build: ./backend
    command: celery -A config flower --port=5555
    ports:
      - "5555:5555"
    env_file:
      - ./backend/.env
    depends_on:
      - redis
      - celery-worker
```

Start:
```bash
docker-compose up -d celery-worker celery-beat flower
```

---

## 📈 Performance Tuning

### Optimize Worker Concurrency

```bash
# Check CPU cores
nproc

# Set concurrency to 2x CPU cores for I/O-bound tasks
celery -A config worker -l info --concurrency=8
```

### Use Separate Workers per Queue

```bash
# Terminal 1: Scanner queue (high priority, low concurrency)
celery -A config worker -l info -Q scanner --concurrency=2

# Terminal 2: Notifications queue (high concurrency)
celery -A config worker -l info -Q notifications --concurrency=4

# Terminal 3: Maintenance queue (low priority)
celery -A config worker -l info -Q maintenance --concurrency=1
```

### Task Priority

```python
# In task definitions
@shared_task(bind=True, priority=9)  # High priority (0-9)
def urgent_task(self):
    pass

@shared_task(bind=True, priority=0)  # Low priority
def background_task(self):
    pass
```

### Result Backend Optimization

```python
# In config/celery.py
app.conf.update(
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={'master_name': 'mymaster'},
)
```

---

## 🔐 Security Best Practices

1. **Use Redis AUTH:**
   ```bash
   # In redis.conf
   requirepass your_strong_password

   # In .env
   REDIS_URL=redis://:your_strong_password@localhost:6379/0
   ```

2. **Restrict Flower Access:**
   ```bash
   celery -A config flower --basic_auth=user:password --port=5555
   ```

3. **Enable SSL for Redis:**
   ```python
   # In config/celery.py
   app.conf.broker_use_ssl = {
       'ssl_cert_reqs': ssl.CERT_REQUIRED,
       'ssl_ca_certs': '/path/to/ca.pem',
   }
   ```

4. **Task Whitelisting:**
   ```python
   # In config/celery.py
   app.conf.task_whitelist = [
       'scanner.tasks.celery_tasks.*',
   ]
   ```

---

## 📚 Additional Resources

- **Celery Documentation:** https://docs.celeryq.dev/
- **Django Celery Beat:** https://django-celery-beat.readthedocs.io/
- **Flower Documentation:** https://flower.readthedocs.io/
- **Redis Documentation:** https://redis.io/documentation

---

## ✅ Verification Checklist

- [ ] Redis is running and accessible
- [ ] Celery worker is running without errors
- [ ] Celery beat is running and triggering tasks
- [ ] Tasks appear in Flower dashboard
- [ ] `scan_binance_market` completes successfully every minute
- [ ] WebSocket broadcasts signals to frontend
- [ ] Database is being updated with new signals
- [ ] Old signals are being cleaned up
- [ ] Health checks show all systems operational
- [ ] Unit tests pass (20/20)

---

**Celery integration is complete and production-ready!** 🚀
