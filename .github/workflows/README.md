# GitHub Actions Workflows

This directory contains automated CI/CD workflows for the Binance Trading Bot.

---

## Workflow: Deploy to Production

**File:** `deploy.yml`

### Trigger Events

- Push to `main` branch
- Manual trigger via GitHub UI

### Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Push to main branch                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      JOB 1: Test                             │
├─────────────────────────────────────────────────────────────┤
│  1. Checkout code                                            │
│  2. Setup Python 3.11                                        │
│  3. Install dependencies                                     │
│  4. Run linting (optional)                                   │
│  5. Check for syntax errors                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼ (if tests pass)
┌─────────────────────────────────────────────────────────────┐
│                    JOB 2: Deploy                             │
├─────────────────────────────────────────────────────────────┤
│  1. Checkout code                                            │
│  2. Create .env files from GitHub Secrets                    │
│  3. Setup SSH key                                            │
│  4. Copy files to server (rsync)                             │
│  5. Copy .env files to server                                │
│  6. Execute deployment script on server:                     │
│     ├─ Backup database                                       │
│     ├─ Stop containers                                       │
│     ├─ Build new images                                      │
│     ├─ Start containers                                      │
│     ├─ Run migrations                                        │
│     ├─ Collect static files                                  │
│     ├─ Restart Celery                                        │
│     └─ Verify health                                         │
│  7. Cleanup SSH keys and .env files                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    JOB 3: Notify                             │
├─────────────────────────────────────────────────────────────┤
│  Send deployment status notification                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Deployment Flow on Server

```
Server: /opt/binance-bot/
│
├─ 1. Backup Database
│   └─ /opt/binance-bot-backups/db_backup_TIMESTAMP.sql
│
├─ 2. Stop Containers
│   └─ docker-compose down
│
├─ 3. Build Images
│   └─ docker-compose build --no-cache
│
├─ 4. Start Containers
│   └─ docker-compose up -d
│       ├─ db (PostgreSQL)
│       ├─ redis (Redis)
│       ├─ web (Django API)
│       ├─ celery (Worker)
│       └─ celery-beat (Scheduler)
│
├─ 5. Run Migrations
│   └─ docker-compose exec web python manage.py migrate
│
├─ 6. Collect Static
│   └─ docker-compose exec web python manage.py collectstatic
│
├─ 7. Restart Celery
│   └─ docker-compose restart celery
│
└─ 8. Verify Health
    └─ curl http://localhost:8000/api/health/
```

---

## Required GitHub Secrets

### Core Secrets
- `SERVER_IP` - Server IP address
- `SERVER_USER` - SSH username (usually `root`)
- `SSH_PRIVATE_KEY` - Private SSH key for authentication

### Application Secrets
- `BINANCE_API_KEY` - Binance API key
- `BINANCE_API_SECRET` - Binance API secret
- `DJANGO_SECRET_KEY` - Django secret key
- `DEBUG` - Debug mode (`False` for production)
- `ALLOWED_HOSTS` - Comma-separated allowed hosts

### Optional Secrets (with defaults)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `CELERY_BROKER_URL` - Celery broker URL
- `CELERY_RESULT_BACKEND` - Celery result backend
- `REACT_APP_API_URL` - Frontend API URL
- `REACT_APP_WS_URL` - WebSocket URL

See [SECRETS_TEMPLATE.md](../SECRETS_TEMPLATE.md) for details.

---

## Workflow Jobs

### Test Job
**Purpose:** Validate code before deployment
**Duration:** ~2 minutes
**Runs on:** Ubuntu latest (GitHub-hosted runner)

**Steps:**
1. Checkout repository code
2. Setup Python 3.11 environment
3. Install Python dependencies
4. Run flake8 linting (optional, continues on error)
5. Compile Python files to check for syntax errors

**Exit conditions:**
- ✅ Success: All syntax checks pass
- ❌ Failure: Syntax errors found (deployment blocked)

### Deploy Job
**Purpose:** Deploy application to production server
**Duration:** ~5 minutes
**Runs on:** Ubuntu latest (GitHub-hosted runner)
**Depends on:** Test job (only runs if tests pass)

**Steps:**
1. **Prepare environment**
   - Checkout code
   - Create .env files from secrets

2. **Setup SSH**
   - Create SSH key file from secret
   - Add server to known hosts

3. **Transfer files**
   - Rsync code to server (excludes .git, node_modules, etc.)
   - Copy .env files separately

4. **Deploy on server** (via SSH)
   - Execute `deploy.sh` script
   - Wait for services to start
   - Verify containers are running
   - Check API health endpoint

5. **Cleanup**
   - Remove SSH key
   - Remove .env files

**Exit conditions:**
- ✅ Success: Health check returns 200 OK
- ❌ Failure: Containers fail to start or health check fails

### Notify Job
**Purpose:** Send deployment status notification
**Duration:** <1 minute
**Runs on:** Ubuntu latest (GitHub-hosted runner)
**Depends on:** Deploy job (always runs)

**Steps:**
1. Check deploy job result
2. Output success/failure message
3. Exit with appropriate code

**Future enhancements:**
- Slack notifications
- Email notifications
- Discord notifications

---

## File Synchronization

### rsync Configuration

**Included directories:**
- `backend/` - Django application
- `client/` - React frontend
- `docker/` - Docker configurations
- `scripts/` - Utility scripts
- `docker-compose.yml`
- `deploy.sh`
- `requirements.txt`
- Other root config files

**Excluded from sync:**
- `.git/` - Git repository data
- `node_modules/` - Node.js dependencies (rebuilt on server)
- `__pycache__/` - Python cache
- `*.pyc` - Compiled Python files
- `.env` - Environment files (copied separately)
- `backtest_data/` - Large historical data
- `docs/` - Documentation

**Why exclude these?**
- Git: Not needed in production
- node_modules: Rebuilt on server for platform compatibility
- Caches: Regenerated automatically
- Data: Too large, managed separately

---

## Deployment Script Details

**File:** `deploy.sh` (runs on server)

### Functions
1. **Backup:** Creates PostgreSQL dump before deployment
2. **Build:** Rebuilds Docker images with latest code
3. **Deploy:** Starts all services
4. **Migrate:** Runs database migrations
5. **Restart:** Restarts workers to load new code
6. **Cleanup:** Removes old Docker images and backups

### Safety Features
- Database backup before changes
- Exit on first error (`set -e`)
- Health verification after deployment
- Rollback capability (restore from backup)

---

## Monitoring Deployment

### On GitHub
1. Go to **Actions** tab
2. Click on running workflow
3. Watch real-time logs
4. View job status and duration

### On Server
```bash
# SSH into server
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f web

# Check container status
docker-compose ps
```

---

## Rollback Procedure

### Automatic (via Git)
```bash
git revert HEAD
git push origin main
# GitHub Actions deploys previous version
```

### Manual (on server)
```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Restore database
docker-compose exec -T db psql -U postgres trading_bot < /opt/binance-bot-backups/db_backup_TIMESTAMP.sql

# Checkout previous commit
git log --oneline
git checkout PREVIOUS_COMMIT_HASH

# Redeploy
./deploy.sh
```

---

## Performance

### Typical Durations
- **Test job:** 1-2 minutes
- **File transfer:** 30 seconds
- **Build:** 2-3 minutes
- **Deployment:** 1-2 minutes
- **Total:** 5-7 minutes

### Optimization Tips
1. Use Docker layer caching
2. Pre-build base images
3. Minimize rsync transfers
4. Run tests in parallel

---

## Security

### Secrets Management
- ✅ All secrets encrypted by GitHub
- ✅ Secrets never logged or exposed
- ✅ SSH keys removed after use
- ✅ .env files not committed to Git

### SSH Security
- Uses key-based authentication (no passwords)
- StrictHostKeyChecking=no (for automation)
- Private keys stored securely in GitHub Secrets
- Keys rotated regularly (recommended)

### Server Security
- Firewall configured (ports 22, 80, 443)
- Docker containers isolated
- Database not exposed externally
- Redis not exposed externally

---

## Troubleshooting

### Common Issues

**1. "Permission denied (publickey)"**
- Check SSH_PRIVATE_KEY is correct in secrets
- Verify public key in server's authorized_keys
- Test SSH locally: `ssh -i ~/.ssh/key root@SERVER_IP`

**2. "rsync: command not found"**
- Install rsync on server: `apt install rsync`

**3. "No such file or directory: /opt/binance-bot"**
- Create directory: `mkdir -p /opt/binance-bot`
- Or run `server-setup.sh`

**4. "Health check failed"**
- Wait longer for services to start
- Check logs: `docker-compose logs web`
- Verify containers running: `docker-compose ps`

**5. "Database migration failed"**
- Check database is running: `docker-compose ps db`
- Check migrations: `docker-compose exec web python manage.py showmigrations`
- Fake migration if needed: `docker-compose exec web python manage.py migrate --fake`

---

## Extending the Workflow

### Add More Tests
Edit `deploy.yml` test job:
```yaml
- name: Run Django Tests
  run: |
    cd backend
    python manage.py test

- name: Run Coverage
  run: |
    pip install coverage
    coverage run --source='.' manage.py test
    coverage report
```

### Add Notifications
```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
    text: |
      Deployment to production: ${{ job.status }}
      Commit: ${{ github.sha }}
      Author: ${{ github.actor }}
```

### Add Staging Environment
Create `deploy-staging.yml`:
```yaml
name: Deploy to Staging

on:
  push:
    branches:
      - develop

jobs:
  deploy:
    # Use staging secrets
    # Deploy to staging server
```

---

## Documentation

- [Deployment Guide](../../DEPLOYMENT.md)
- [Quick Start](../../CICD_QUICKSTART.md)
- [Secrets Template](../SECRETS_TEMPLATE.md)
- [Project README](../../README.md)

---

**Last Updated**: 2025-11-10
