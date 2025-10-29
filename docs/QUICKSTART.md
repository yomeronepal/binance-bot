# 🚀 Binance Bot - Quick Start Guide

Get your Binance trading bot running in 5 minutes!

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Docker (optional)

---

## Option 1: Docker Setup (Recommended)

### 1. Clone and Configure

```bash
git clone <your-repo>
cd binance-bot

# Copy environment files
cp backend/.env.example backend/.env
cp client/.env.example client/.env

# Edit backend/.env with your settings
nano backend/.env
```

### 2. Start All Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Django backend (port 8000)
- React frontend (port 5173)
- Celery worker
- Celery beat
- Flower monitoring (port 5555)

### 3. Initialize Database

```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

### 4. Access Applications

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000/api/
- **Django Admin:** http://localhost:8000/admin/
- **Flower (Celery):** http://localhost:5555
- **WebSocket:** ws://localhost:8000/ws/signals/

---

## Option 2: Manual Setup

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### 2. Frontend Setup

```bash
cd client

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### 3. Start Services

You need **6 terminals**:

#### Terminal 1: PostgreSQL
```bash
# If not using Docker
pg_ctl -D /usr/local/var/postgres start
```

#### Terminal 2: Redis
```bash
redis-server
```

#### Terminal 3: Django Backend
```bash
cd backend
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

#### Terminal 4: Celery Worker
```bash
cd backend
source venv/bin/activate
celery -A config worker -l info -Q scanner,notifications,maintenance
```

#### Terminal 5: Celery Beat
```bash
cd backend
source venv/bin/activate
celery -A config beat -l info
```

#### Terminal 6: React Frontend
```bash
cd client
npm run dev
```

#### Terminal 7 (Optional): Flower Monitoring
```bash
cd backend
source venv/bin/activate
celery -A config flower --port=5555
```

---

## 🧪 Verify Installation

### 1. Check Backend Health

```bash
curl http://localhost:8000/api/health/
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### 2. Test WebSocket Connection

Open browser console at http://localhost:5173 and run:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/signals/');
ws.onopen = () => console.log('✅ WebSocket connected');
ws.onmessage = (e) => console.log('📨 Message:', JSON.parse(e.data));
```

### 3. Test Celery Tasks

```bash
cd backend
python manage.py shell
```

```python
from scanner.tasks.celery_tasks import test_celery_task, system_health_check

# Test simple task
result = test_celery_task.delay("Hello!")
print(result.get())  # Should print success message

# Test health check
health = system_health_check.delay()
print(health.get())  # Should show system status
```

### 4. Run Unit Tests

```bash
# Backend tests
cd backend
pytest -v

# Expected: 50+ tests passed
```

---

## 📊 Access Dashboard

1. Navigate to http://localhost:5173
2. You should see the real-time trading signals dashboard
3. Check the connection status badge (should be green)
4. Signals will appear automatically as they're generated

---

## 🔧 Common Issues

### Issue: "Connection refused" errors

**Check services are running:**
```bash
# Check PostgreSQL
psql -U postgres -c "SELECT 1;"

# Check Redis
redis-cli ping

# Check Django
curl http://localhost:8000/api/health/
```

### Issue: No signals appearing

**Manually trigger scanner:**
```python
# In Django shell
from scanner.tasks.celery_tasks import scan_binance_market

result = scan_binance_market.delay()
print(result.get(timeout=120))
```

### Issue: WebSocket not connecting

**Check CORS settings in `backend/config/settings.py`:**
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Must match frontend URL
]
```

### Issue: Celery tasks not running

**Check Celery worker logs:**
```bash
# Should see:
# [tasks]
#   . scanner.tasks.celery_tasks.scan_binance_market
#   . scanner.tasks.celery_tasks.full_data_refresh
#   ...
```

**Check Celery beat is scheduling tasks:**
```bash
# Should see periodic messages like:
# Scheduler: Sending due task scan-binance-market
```

---

## 📈 Next Steps

### 1. Configure Binance API (Optional)

For authenticated endpoints:

```bash
# In backend/.env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

### 2. Customize Signal Detection

Edit thresholds in `backend/scanner/strategies/signal_engine.py`:

```python
config = SignalConfig(
    min_confidence=0.75,  # Increase for fewer, higher-quality signals
    long_rsi_min=55.0,    # Adjust RSI thresholds
    long_rsi_max=75.0,
    sl_atr_multiplier=2.0,  # Wider stop loss
    tp_atr_multiplier=3.0,  # Larger profit target
)
```

### 3. Monitor Performance

**Flower Dashboard:** http://localhost:5555
- View task execution times
- Check success/failure rates
- Monitor worker health

**Django Admin:** http://localhost:8000/admin/
- View signals in database
- Check periodic task schedules
- Monitor user activity

### 4. Adjust Scanning Frequency

Edit `backend/config/celery.py`:

```python
app.conf.beat_schedule = {
    'scan-binance-market': {
        'task': 'scanner.tasks.celery_tasks.scan_binance_market',
        'schedule': 30.0,  # Change from 60 to 30 seconds
    },
}
```

### 5. Scale Workers

```bash
# Increase concurrency for faster processing
celery -A config worker -l info -Q scanner,notifications,maintenance --concurrency=8

# Or run multiple workers
celery -A config worker -l info -Q scanner --concurrency=2 -n worker1@%h
celery -A config worker -l info -Q notifications --concurrency=4 -n worker2@%h
```

---

## 📚 Documentation

- **[Signal Engine Integration](./SIGNAL_ENGINE_INTEGRATION.md)** - How signals are generated and updated
- **[Celery Setup](./CELERY_SETUP.md)** - Detailed Celery configuration and troubleshooting
- **[Scanner Quickstart](./SCANNER_QUICKSTART.md)** - Scanner-specific documentation
- **[API Documentation](./backend/API.md)** - REST API endpoints

---

## 🎯 Expected Behavior

Once everything is running:

1. **Every 60 seconds:**
   - Celery triggers `scan_binance_market` task
   - Fetches data for top 50 USDT pairs
   - Calculates technical indicators
   - Generates/updates/removes signals
   - Broadcasts changes via WebSocket
   - Frontend updates automatically

2. **Every hour:**
   - Marks signals older than 1 hour as EXPIRED

3. **Every 2 minutes:**
   - Broadcasts high-confidence signals (≥85%)

4. **Every 5 minutes:**
   - Cleans up signals older than 24 hours

5. **Every 10 minutes:**
   - Runs system health check

### Typical Logs

**Celery Worker:**
```
[2025-10-29 12:00:00] Task scanner.tasks.celery_tasks.scan_binance_market[...] received
🔄 Starting Binance market scan...
📊 Monitoring 50 top volume pairs
✅ Market scan completed: Created=2, Updated=5, Deleted=1, Active=15
[2025-10-29 12:00:12] Task scanner.tasks.celery_tasks.scan_binance_market[...] succeeded in 12.3s
```

**Frontend Console:**
```
✅ WebSocket connected
📨 Message: {type: "signal_created", signal: {...}}
📨 Message: {type: "signal_updated", signal: {...}}
```

---

## ✅ System Health Checklist

- [ ] PostgreSQL is running and accessible
- [ ] Redis is running (test with `redis-cli ping`)
- [ ] Django backend is running (test with `curl http://localhost:8000/api/health/`)
- [ ] React frontend is accessible at http://localhost:5173
- [ ] WebSocket connects successfully (green badge on dashboard)
- [ ] Celery worker is running and consuming tasks
- [ ] Celery beat is scheduling periodic tasks
- [ ] Signals appear on the dashboard
- [ ] Flower shows tasks executing successfully
- [ ] No errors in console logs

---

**You're all set! The bot is now scanning Binance markets and generating trading signals in real-time.** 🎉

For issues or questions, check the troubleshooting sections in the detailed documentation.
