# Log Monitoring Dashboard

Complete guide for monitoring logs from Django, Celery Worker, and Celery Beat using Dozzle.

---

## Overview

The application now includes **Dozzle** - a lightweight, real-time log viewer for Docker containers with a beautiful web UI.

### Features

✅ **Real-time log streaming** - See logs as they happen
✅ **Multi-container support** - Monitor all containers in one place
✅ **Search & filter** - Find specific log entries quickly
✅ **Dark/Light theme** - Easy on the eyes
✅ **No authentication needed** - Simple access (secure it if public)
✅ **Lightweight** - Minimal resource usage
✅ **Auto-refresh** - Logs update automatically

---

## Quick Start

### Access the Dashboard

Once deployed, access Dozzle at:

```
http://YOUR_SERVER_IP:3000
```

**Default port:** `3000`

### Services Monitored

The dashboard shows logs from:

1. **binancebot_web** - Django/Daphne application logs
2. **binancebot_celery** - Celery worker logs (background tasks)
3. **binancebot_celery_beat** - Celery beat logs (scheduled tasks)
4. **binancebot_db** - PostgreSQL database logs
5. **binancebot_redis** - Redis cache logs
6. **binancebot_frontend** - React frontend logs

---

## Using Dozzle

### Main Interface

When you open Dozzle, you'll see:

```
┌─────────────────────────────────────────────────────┐
│  Dozzle - Docker Log Viewer                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Containers:                     Search: [____]    │
│  ✓ binancebot_web                                  │
│  ✓ binancebot_celery                               │
│  ✓ binancebot_celery_beat                          │
│  ✓ binancebot_db                                   │
│  ✓ binancebot_redis                                │
│  ✓ binancebot_frontend                             │
│                                                     │
│  ┌─── Logs ─────────────────────────────────────┐ │
│  │ [2025-11-10 18:30:45] INFO: Task started    │ │
│  │ [2025-11-10 18:30:46] DEBUG: Processing...  │ │
│  │ [2025-11-10 18:30:47] INFO: Task completed  │ │
│  └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Viewing Logs

**1. Select a Container**
- Click on any container name to view its logs
- Logs appear in real-time below

**2. Multi-Container View**
- Click multiple containers to see combined logs
- Useful for debugging interactions

**3. Search Logs**
- Use the search box to filter logs
- Supports regex patterns

**4. Download Logs**
- Click the download icon to save logs locally
- Great for sharing with team or analysis

---

## Log Configuration

### Log Rotation

All services are configured with automatic log rotation:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"      # Max file size: 10 MB
    max-file: "3"        # Keep 3 files
    labels: "service=web"
```

**What this means:**
- Logs rotate when they reach 10 MB
- Only the last 3 rotated files are kept
- Total max storage per service: ~30 MB
- Prevents disk space issues

### Log Levels

**Django (web):**
- INFO - Application events
- WARNING - Potential issues
- ERROR - Errors that need attention
- CRITICAL - Critical failures

**Celery (worker & beat):**
- INFO - Task execution status
- WARNING - Retries and failures
- ERROR - Task errors
- DEBUG - Detailed task information

---

## Common Use Cases

### 1. Debugging Django Errors

**View Django logs:**
1. Open Dozzle: `http://YOUR_SERVER_IP:8888`
2. Click **binancebot_web**
3. Search for "ERROR" or "Exception"

**Example log:**
```
[2025-11-10 18:30:45] ERROR: Exception in view: /api/signals/
Traceback (most recent call last):
  File "/app/views.py", line 42, in get_signals
    ...
```

### 2. Monitoring Celery Tasks

**View Celery worker logs:**
1. Click **binancebot_celery**
2. Search for task name or "Task"

**Example log:**
```
[2025-11-10 18:30:45] INFO: Task signals.tasks.process_signal[123] received
[2025-11-10 18:30:46] INFO: Task signals.tasks.process_signal[123] succeeded in 1.2s
```

### 3. Checking Scheduled Tasks

**View Celery beat logs:**
1. Click **binancebot_celery_beat**
2. See scheduler activity

**Example log:**
```
[2025-11-10 18:30:00] INFO: Scheduler: Sending due task scanner.tasks.scan_market
[2025-11-10 18:35:00] INFO: Scheduler: Sending due task maintenance.tasks.cleanup_old_data
```

### 4. Database Issues

**View PostgreSQL logs:**
1. Click **binancebot_db**
2. Look for slow queries or errors

**Example log:**
```
[2025-11-10 18:30:45] LOG: duration: 1523.456 ms  statement: SELECT * FROM signals...
[2025-11-10 18:30:46] ERROR: deadlock detected
```

### 5. Multi-Service Debugging

**View combined logs:**
1. Select **binancebot_web** + **binancebot_celery**
2. See request-to-task flow
3. Trace issues across services

---

## Advanced Features

### 1. Filtering Logs

**By log level:**
```
Search: ERROR
Search: WARNING
Search: INFO
```

**By time:**
```
Search: 18:30
Search: 2025-11-10
```

**By task/signal:**
```
Search: scan_market
Search: backtest
Search: paper_trading
```

**Using regex:**
```
Search: Task.*succeeded
Search: Exception.*view
```

### 2. Live Tail

Dozzle automatically tails logs in real-time. New logs appear instantly at the bottom.

**Pause/Resume:**
- Click the pause button to stop auto-scrolling
- Useful for reading specific logs
- Click play to resume

### 3. Container Stats

Hover over container names to see:
- Container ID
- Status (running/stopped)
- Uptime

### 4. Multiple Tabs

Open multiple browser tabs to:
- Monitor different containers simultaneously
- Compare logs side-by-side

---

## Security

### Production Security

**Important:** Dozzle has no built-in authentication!

**Option 1: Firewall (Recommended)**
```bash
# Only allow access from specific IPs
sudo ufw allow from YOUR_IP to any port 3000
sudo ufw deny 3000
```

**Option 2: Reverse Proxy with Auth**

Use Nginx with basic auth:

```nginx
server {
    listen 80;
    server_name logs.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
```

**Option 3: VPN/SSH Tunnel**
```bash
# Access via SSH tunnel
ssh -L 3000:localhost:3000 root@YOUR_SERVER_IP

# Then open: http://localhost:3000
```

**Option 4: Disable Public Access**

Only access from server:
```yaml
ports:
  - "127.0.0.1:3000:8080"  # Only localhost
```

---

## Troubleshooting

### Can't Access Dozzle

**Problem:** Cannot open `http://YOUR_SERVER_IP:3000`

**Solutions:**
1. Check container is running:
   ```bash
   docker ps | grep dozzle
   ```

2. Check port is open:
   ```bash
   sudo ufw status
   sudo ufw allow 3000
   ```

3. Check logs:
   ```bash
   docker logs binancebot_dozzle
   ```

### No Logs Showing

**Problem:** Container shows but no logs appear

**Solutions:**
1. Container might be newly started (no logs yet)
2. Check container is running:
   ```bash
   docker compose ps
   ```

3. Generate some logs:
   ```bash
   docker compose restart web
   ```

### Dozzle Container Keeps Restarting

**Problem:** Dozzle won't stay running

**Solution:**
```bash
# Check logs
docker logs binancebot_dozzle

# Common issue: Docker socket permission
sudo chmod 666 /var/run/docker.sock
```

### Logs Not Rotating

**Problem:** Log files getting too large

**Solution:**
```bash
# Check current log sizes
docker inspect --format='{{.LogPath}}' binancebot_web | xargs ls -lh

# Force log rotation
docker compose restart web
```

---

## CLI Alternatives

### View Logs Without Dashboard

**Single container:**
```bash
# View all logs
docker compose logs web

# Follow logs (live)
docker compose logs -f web

# Last 100 lines
docker compose logs --tail=100 web

# Since timestamp
docker compose logs --since=10m web
```

**Multiple containers:**
```bash
# All services
docker compose logs -f

# Specific services
docker compose logs -f web celery celery-beat
```

**Search logs:**
```bash
# Grep for errors
docker compose logs web | grep ERROR

# Grep for specific task
docker compose logs celery | grep scan_market
```

---

## Log Levels Configuration

### Django Log Levels

Edit `backend/config/settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',  # Change to DEBUG for more detail
    },
}
```

### Celery Log Levels

Change worker command in `docker-compose.prod.yml`:

```yaml
# More verbose
command: celery -A config worker -l debug

# Less verbose
command: celery -A config worker -l warning
```

**Available levels:**
- `debug` - Very detailed
- `info` - Standard (recommended)
- `warning` - Only warnings and errors
- `error` - Only errors
- `critical` - Only critical issues

---

## Performance Tips

### 1. Limit Log Size

Already configured with 10MB max per file, 3 files total.

### 2. Adjust Tail Size

Edit Dozzle environment in `docker-compose.prod.yml`:

```yaml
environment:
  - DOZZLE_TAILSIZE=500  # Show last 500 lines (default: 300)
```

### 3. Filter Containers

Only monitor specific containers:

```yaml
environment:
  - DOZZLE_FILTER=name=binancebot_web|binancebot_celery
```

### 4. Disable Analytics

Already configured:
```yaml
environment:
  - DOZZLE_NO_ANALYTICS=true
```

---

## Integration with Monitoring

### Export Logs to External Service

**To Sentry (errors):**
```python
# Install sentry-sdk
pip install sentry-sdk

# Add to settings.py
import sentry_sdk
sentry_sdk.init(dsn="YOUR_SENTRY_DSN")
```

**To ELK Stack:**
```yaml
logging:
  driver: "gelf"
  options:
    gelf-address: "udp://logstash:12201"
```

**To CloudWatch:**
```yaml
logging:
  driver: "awslogs"
  options:
    awslogs-region: "us-east-1"
    awslogs-group: "binance-bot"
```

---

## Quick Reference

### Ports

| Service | Port | Description |
|---------|------|-------------|
| Dozzle | 3000 | Log monitoring dashboard |
| Django | 8000 | API/Web application |
| Frontend | 5173 | React frontend |
| PostgreSQL | 5432 | Database (internal) |
| Redis | 6379 | Cache (internal) |

### Common Searches

| Search | Purpose |
|--------|---------|
| `ERROR` | Find errors |
| `Task.*succeeded` | Find completed tasks |
| `Task.*failed` | Find failed tasks |
| `scan_market` | Find scanner tasks |
| `backtest` | Find backtest tasks |
| `paper_trading` | Find paper trading tasks |
| `Exception` | Find exceptions |
| `Traceback` | Find stack traces |

### Useful Commands

```bash
# Start Dozzle
docker compose up -d dozzle

# Restart Dozzle
docker compose restart dozzle

# Stop Dozzle
docker compose stop dozzle

# View Dozzle logs
docker logs binancebot_dozzle

# Access Dozzle shell
docker exec -it binancebot_dozzle sh
```

---

## Maintenance

### Weekly Tasks

1. **Check log sizes:**
   ```bash
   docker system df
   ```

2. **Review errors:**
   - Open Dozzle
   - Search for "ERROR"
   - Address recurring issues

### Monthly Tasks

1. **Clean old logs:**
   ```bash
   docker system prune -f
   ```

2. **Review log rotation:**
   - Check disk space
   - Adjust max-size if needed

3. **Update Dozzle:**
   ```bash
   docker compose pull dozzle
   docker compose up -d dozzle
   ```

---

## Summary

**Access:** `http://YOUR_SERVER_IP:3000`

**Features:**
- ✅ Real-time log streaming
- ✅ Multi-container monitoring
- ✅ Search and filter
- ✅ Automatic log rotation
- ✅ Lightweight and fast

**Monitored Services:**
- Django (web)
- Celery worker
- Celery beat
- PostgreSQL
- Redis
- Frontend

**Security:** Add firewall rules or use SSH tunnel for production

---

**Last Updated:** 2025-11-10
