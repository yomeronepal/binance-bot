# 🐳 Docker Deployment Guide - Binance Trading Bot

Complete guide for deploying the Binance Trading Bot using Docker.

---

## 📋 Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Docker Compose** v2.0+
- **8GB RAM** minimum (16GB recommended)
- **10GB free disk space**

---

## 🚀 Quick Start

### Windows Users

1. Open PowerShell or Command Prompt
2. Navigate to project directory:
   ```cmd
   cd D:\Project\binance-bot
   ```

3. Run the startup script:
   ```cmd
   start.bat
   ```

### Linux/Mac Users

1. Open Terminal
2. Navigate to project directory:
   ```bash
   cd /path/to/binance-bot
   ```

3. Make script executable and run:
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

---

## 🛠️ Manual Setup

If you prefer manual control:

### Step 1: Environment Configuration

Ensure `.env` files are configured:

**backend/.env:**
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgres://binancebot:binancebot123@postgres:5432/binancebot
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Scanner Configuration
BINANCE_INTERVAL=5m
POLLING_INTERVAL=60
MIN_CONFIDENCE=0.7
TOP_PAIRS=50
```

**client/.env:**
```env
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/signals/
```

### Step 2: Build Images

```bash
docker-compose build
```

This will build:
- `binance-bot-backend` - Django + Daphne
- `binance-bot-celery-worker` - Background worker
- `binance-bot-celery-beat` - Task scheduler
- `binance-bot-flower` - Monitoring dashboard
- `binance-bot-frontend` - React app

### Step 3: Start Database & Redis

```bash
docker-compose up -d postgres redis
```

Wait for services to be healthy (about 10 seconds):
```bash
docker-compose ps
```

### Step 4: Run Migrations

```bash
docker-compose run --rm backend python manage.py migrate
```

Expected output:
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, sessions, users, signals, billing, scanner...
Running migrations:
  Applying ...
```

### Step 5: Create Superuser

```bash
docker-compose run --rm backend python manage.py createsuperuser
```

Follow the prompts to create an admin user.

### Step 6: Start All Services

```bash
docker-compose up -d
```

This starts:
- `postgres` - PostgreSQL database
- `redis` - Redis cache/broker
- `backend` - Django backend
- `celery-worker` - Background tasks
- `celery-beat` - Periodic scheduler
- `flower` - Celery monitoring
- `frontend` - React frontend

---

## 🌐 Access Applications

Once all services are running:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:5173 | Trading dashboard |
| **Backend API** | http://localhost:8000/api/ | REST API endpoints |
| **Django Admin** | http://localhost:8000/admin/ | Admin panel |
| **Flower** | http://localhost:5555 | Celery monitoring |
| **WebSocket** | ws://localhost:8000/ws/signals/ | Real-time updates |

---

## 📊 Verify Installation

### Check Service Status

```bash
docker-compose ps
```

Expected output (all services should be "Up"):
```
NAME                      STATUS               PORTS
binance-bot-backend       Up (healthy)         0.0.0.0:8000->8000/tcp
binance-bot-celery-beat   Up
binance-bot-celery-worker Up
binance-bot-flower        Up                   0.0.0.0:5555->5555/tcp
binance-bot-frontend      Up                   0.0.0.0:5173->5173/tcp
binance-bot-postgres      Up (healthy)         0.0.0.0:5432->5432/tcp
binance-bot-redis         Up (healthy)         0.0.0.0:6379->6379/tcp
```

### Check Backend Health

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

### Check Celery Tasks

Open Flower at http://localhost:5555:
- Navigate to "Tasks" tab
- You should see periodic tasks running
- Check "Workers" tab for worker status

### Test Frontend

1. Open http://localhost:5173
2. You should see the trading dashboard
3. Check the connection status badge (should be green)
4. Open browser console - no errors should appear

---

## 📝 Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f celery-worker
docker-compose logs -f frontend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart celery-worker
```

### Stop Services

```bash
# Stop all (keeps containers)
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove everything (including volumes)
docker-compose down -v
```

### Execute Commands in Containers

```bash
# Django shell
docker-compose exec backend python manage.py shell

# Create migrations
docker-compose exec backend python manage.py makemigrations

# Collect static files
docker-compose exec backend python manage.py collectstatic

# Run tests
docker-compose exec backend pytest -v
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U binancebot -d binancebot

# Backup database
docker-compose exec postgres pg_dump -U binancebot binancebot > backup.sql

# Restore database
docker-compose exec -T postgres psql -U binancebot binancebot < backup.sql
```

### Redis Operations

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Check keys
docker-compose exec redis redis-cli KEYS "*"

# Flush all data
docker-compose exec redis redis-cli FLUSHALL
```

---

## 🔧 Troubleshooting

### Issue 1: Port Already in Use

**Error:** `bind: address already in use`

**Solution:**
```bash
# Check what's using the port
# Windows:
netstat -ano | findstr :8000

# Linux/Mac:
lsof -i :8000

# Kill the process or change port in docker-compose.yml
```

### Issue 2: Database Connection Refused

**Symptoms:** Backend can't connect to database

**Solution:**
```bash
# Check if postgres is healthy
docker-compose ps postgres

# View postgres logs
docker-compose logs postgres

# Restart postgres
docker-compose restart postgres

# Wait for health check
sleep 10
```

### Issue 3: Celery Tasks Not Running

**Symptoms:** No tasks visible in Flower

**Solution:**
```bash
# Check celery-worker logs
docker-compose logs celery-worker

# Check celery-beat logs
docker-compose logs celery-beat

# Restart Celery services
docker-compose restart celery-worker celery-beat

# Verify Redis is running
docker-compose exec redis redis-cli PING
```

### Issue 4: Frontend Not Loading

**Symptoms:** Blank page or build errors

**Solution:**
```bash
# Check frontend logs
docker-compose logs frontend

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend

# Check if port 5173 is accessible
curl http://localhost:5173
```

### Issue 5: WebSocket Connection Fails

**Symptoms:** Dashboard shows "Disconnected"

**Solution:**
```bash
# Check backend WebSocket support
docker-compose logs backend | grep -i websocket

# Verify Daphne is running (not gunicorn)
docker-compose exec backend ps aux | grep daphne

# Test WebSocket connection
wscat -c ws://localhost:8000/ws/signals/
```

### Issue 6: Build Fails

**Symptoms:** Docker build errors

**Solution:**
```bash
# Clean Docker system
docker system prune -a

# Remove old images
docker rmi $(docker images -q binance-bot-*)

# Build with no cache
docker-compose build --no-cache

# Check disk space
df -h  # Linux/Mac
wmic logicaldisk get size,freespace,caption  # Windows
```

---

## 🔒 Security Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` in backend/.env to a strong random value
- [ ] Set `DEBUG=False` in production
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Use strong database password (not `binancebot123`)
- [ ] Enable HTTPS/SSL with reverse proxy (Nginx)
- [ ] Configure firewall rules
- [ ] Set up Redis password authentication
- [ ] Restrict Flower access (add basic auth)
- [ ] Regular database backups
- [ ] Monitor logs for security issues

---

## 📈 Performance Optimization

### For Development

```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### For Production

1. **Use production-ready web server:**
   ```dockerfile
   # Replace Daphne with gunicorn + uvicorn workers
   CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker"]
   ```

2. **Scale Celery workers:**
   ```bash
   docker-compose up -d --scale celery-worker=4
   ```

3. **Add Nginx reverse proxy:**
   ```yaml
   services:
     nginx:
       image: nginx:alpine
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./nginx.conf:/etc/nginx/nginx.conf
   ```

4. **Use Docker Swarm or Kubernetes** for orchestration

---

## 📦 Backup & Restore

### Backup Everything

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup database
docker-compose exec postgres pg_dump -U binancebot binancebot > backups/$(date +%Y%m%d)/database.sql

# Backup volumes
docker run --rm -v binance-bot_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/$(date +%Y%m%d)/postgres_data.tar.gz /data

# Backup .env files
cp backend/.env backups/$(date +%Y%m%d)/backend.env
cp client/.env backups/$(date +%Y%m%d)/client.env
```

### Restore from Backup

```bash
# Stop services
docker-compose down

# Restore database
docker-compose up -d postgres
sleep 10
docker-compose exec -T postgres psql -U binancebot binancebot < backups/20250129/database.sql

# Restore volumes
docker run --rm -v binance-bot_postgres_data:/data -v $(pwd)/backups:/backup alpine tar xzf /backup/20250129/postgres_data.tar.gz -C /

# Start services
docker-compose up -d
```

---

## 🎯 Next Steps

1. **Monitor application:** http://localhost:5555 (Flower)
2. **Check signals:** http://localhost:5173 (Dashboard)
3. **Review logs:** `docker-compose logs -f`
4. **Configure scanner:** Edit `backend/.env` for custom settings
5. **Set up alerts:** Configure notifications for high-confidence signals
6. **Scale workers:** Increase Celery concurrency for more pairs

---

## 📞 Support

If you encounter issues:

1. Check logs: `docker-compose logs --tail=100`
2. Review troubleshooting section above
3. Verify all prerequisites are met
4. Check Docker resources (CPU/RAM/Disk)
5. Ensure no firewall blocking ports

---

**Your Binance Trading Bot is now fully integrated and production-ready!** 🎉

All services are running in Docker containers with:
- ✅ Automatic restarts
- ✅ Health checks
- ✅ Volume persistence
- ✅ Celery background tasks
- ✅ Real-time WebSocket updates
- ✅ Monitoring dashboard
