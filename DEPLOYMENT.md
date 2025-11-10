# Deployment Guide - CI/CD with GitHub Actions

This guide explains how to set up automated deployment to your server using GitHub Actions.

---

## Overview

The CI/CD pipeline automatically:
1. Runs tests when you push to `main` branch
2. Connects to your server via SSH
3. Copies files using rsync
4. Builds and restarts Docker containers
5. Runs database migrations
6. Verifies deployment health

---

## Prerequisites

### On Your Server

1. **Install Docker and Docker Compose**
   ```bash
   # Update packages
   apt update && apt upgrade -y

   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh

   # Install Docker Compose
   apt install docker-compose -y

   # Verify installation
   docker --version
   docker-compose --version
   ```

2. **Create project directory**
   ```bash
   mkdir -p /opt/binance-bot
   mkdir -p /opt/binance-bot-backups
   ```

3. **Setup SSH access**
   ```bash
   # If you don't have an SSH key, generate one on your local machine
   ssh-keygen -t ed25519 -C "github-actions-deploy"
   # Save to: ~/.ssh/github_deploy_key

   # Copy the PUBLIC key to your server
   ssh-copy-id -i ~/.ssh/github_deploy_key.pub root@YOUR_SERVER_IP

   # Or manually add to server's authorized_keys:
   cat ~/.ssh/github_deploy_key.pub | ssh root@YOUR_SERVER_IP 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'
   ```

4. **Test SSH connection**
   ```bash
   ssh -i ~/.ssh/github_deploy_key root@YOUR_SERVER_IP
   ```

### On GitHub

You need to add the following secrets to your GitHub repository.

---

## GitHub Secrets Setup

Go to your repository on GitHub:
**Settings → Secrets and variables → Actions → New repository secret**

### Required Secrets

#### 1. Server Connection
| Secret Name | Description | Example |
|-------------|-------------|---------|
| `SERVER_IP` | Your server IP address | `192.168.1.100` |
| `SERVER_USER` | SSH username (usually `root`) | `root` |
| `SSH_PRIVATE_KEY` | Your private SSH key | Contents of `~/.ssh/github_deploy_key` |

**How to get SSH_PRIVATE_KEY:**
```bash
cat ~/.ssh/github_deploy_key
```
Copy the entire output (including `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----`)

#### 2. Application Secrets (Backend)
| Secret Name | Description | Example |
|-------------|-------------|---------|
| `BINANCE_API_KEY` | Your Binance API key | `abc123...` |
| `BINANCE_API_SECRET` | Your Binance API secret | `xyz789...` |
| `DJANGO_SECRET_KEY` | Django secret key | `generate-random-50-char-string` |
| `DEBUG` | Debug mode (use `False` in production) | `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `your-domain.com,192.168.1.100` |

**Generate Django Secret Key:**
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### 3. Optional Secrets (with defaults)
| Secret Name | Description | Default |
|-------------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@db:5432/trading_bot` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://redis:6379/0` |
| `REACT_APP_API_URL` | Frontend API URL | `http://localhost:8000` |
| `REACT_APP_WS_URL` | WebSocket URL | `ws://localhost:8000` |

---

## Initial Server Setup

Before your first deployment, manually set up the server:

```bash
# 1. SSH into your server
ssh root@YOUR_SERVER_IP

# 2. Create project directory
mkdir -p /opt/binance-bot
cd /opt/binance-bot

# 3. Clone your repository (first time only)
git clone https://github.com/YOUR_USERNAME/binance-bot.git .

# 4. Create .env files (GitHub Actions will overwrite these)
cp backend/.env.example backend/.env
cp client/.env.example client/.env

# 5. Edit .env files with your credentials
nano backend/.env
nano client/.env

# 6. Make deployment script executable
chmod +x deploy.sh

# 7. Initial deployment
docker-compose up -d --build

# 8. Run migrations
docker-compose exec web python manage.py migrate

# 9. Create superuser
docker-compose exec web python manage.py createsuperuser

# 10. Download historical data (optional)
docker-compose exec web python scripts/data/download_long_period.py
```

---

## How to Deploy

### Automatic Deployment

Simply push to the `main` branch:

```bash
git add .
git commit -m "Your commit message"
git push origin main
```

GitHub Actions will automatically:
1. Run tests
2. Deploy to your server
3. Restart services

### Manual Deployment

Trigger deployment manually from GitHub:
1. Go to **Actions** tab in your repository
2. Click **Deploy to Production**
3. Click **Run workflow**
4. Select `main` branch
5. Click **Run workflow**

---

## Monitoring Deployment

### On GitHub

1. Go to **Actions** tab
2. Click on the running workflow
3. Watch the live logs

### On Your Server

```bash
# SSH into server
ssh root@YOUR_SERVER_IP

# Watch deployment logs
cd /opt/binance-bot
docker-compose logs -f

# Check container status
docker-compose ps

# Check specific service logs
docker-compose logs -f web
docker-compose logs -f celery
docker-compose logs -f redis
```

---

## Troubleshooting

### Deployment Fails at SSH Connection

**Problem:** `Permission denied (publickey)`

**Solution:**
1. Verify SSH key is correct:
   ```bash
   ssh -i ~/.ssh/github_deploy_key root@YOUR_SERVER_IP
   ```
2. Check that the PRIVATE key is in GitHub Secrets (not the public key)
3. Ensure server's `~/.ssh/authorized_keys` contains the PUBLIC key

### Deployment Fails at "Copy files to server"

**Problem:** `rsync: command not found`

**Solution:** Install rsync on server:
```bash
ssh root@YOUR_SERVER_IP
apt install rsync -y
```

### Containers Fail to Start

**Problem:** Containers exit immediately

**Solution:**
```bash
# Check logs
docker-compose logs

# Common issues:
# 1. Port already in use - kill existing process
sudo lsof -i :8000
sudo kill -9 PID

# 2. Database connection issues
docker-compose exec web python manage.py migrate

# 3. Permission issues
chmod -R 755 /opt/binance-bot
```

### Database Migration Errors

**Problem:** `relation "table_name" already exists`

**Solution:**
```bash
# Fake the migration
docker-compose exec web python manage.py migrate --fake

# Or reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
docker-compose exec web python manage.py migrate
```

### Health Check Fails

**Problem:** `curl: (7) Failed to connect to localhost:8000`

**Solution:**
```bash
# Check if web container is running
docker-compose ps

# Check web container logs
docker-compose logs web

# Common causes:
# 1. Container still starting - wait 30 seconds
# 2. Port not exposed - check docker-compose.yml
# 3. Firewall blocking - check ufw status
```

---

## Rollback Procedure

If deployment breaks production:

### Option 1: Rollback via Git

```bash
# On your local machine
git revert HEAD
git push origin main

# GitHub Actions will automatically deploy the previous version
```

### Option 2: Manual Rollback on Server

```bash
# SSH into server
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Restore database backup
docker-compose exec -T db psql -U postgres trading_bot < /opt/binance-bot-backups/db_backup_TIMESTAMP.sql

# Checkout previous commit
git log --oneline  # Find previous commit hash
git checkout PREVIOUS_COMMIT_HASH

# Redeploy
./deploy.sh
```

---

## Advanced Configuration

### Deploy to Staging First

Create a staging workflow:

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy to Staging

on:
  push:
    branches:
      - develop

jobs:
  deploy:
    # Same as deploy.yml but use staging secrets
    # SERVER_IP_STAGING, etc.
```

### Add Slack Notifications

Add to your workflow:

```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Run Tests Before Deploy

The workflow already includes a `test` job. Expand it:

```yaml
jobs:
  test:
    steps:
      - name: Run Django tests
        run: |
          cd backend
          python manage.py test

      - name: Run frontend tests
        run: |
          cd client
          npm install
          npm test
```

---

## Security Best Practices

1. **Never commit secrets** - Always use GitHub Secrets
2. **Use SSH keys** - Don't use password authentication
3. **Restrict SSH access** - Only allow specific IPs if possible
4. **Keep backups** - Deployment script automatically backs up database
5. **Use HTTPS** - Set up SSL/TLS certificates (use Let's Encrypt)
6. **Monitor logs** - Set up log aggregation (ELK, Grafana)
7. **Update regularly** - Keep dependencies and Docker images updated

---

## Production Checklist

Before going live:

- [ ] All GitHub Secrets configured
- [ ] SSH access working
- [ ] Server has Docker and Docker Compose installed
- [ ] Firewall configured (allow ports 80, 443, 22)
- [ ] SSL certificate configured (use Certbot)
- [ ] Database backups enabled
- [ ] Monitoring set up (Sentry, Datadog, etc.)
- [ ] Environment variables set to production values (`DEBUG=False`)
- [ ] ALLOWED_HOSTS configured correctly
- [ ] Static files served correctly
- [ ] Celery workers running
- [ ] Redis configured with persistence
- [ ] Health checks passing

---

## Maintenance

### Update Dependencies

```bash
# On your local machine
cd backend
pip list --outdated
pip install --upgrade PACKAGE_NAME

# Update requirements.txt
pip freeze > requirements.txt

# Commit and push
git add requirements.txt
git commit -m "Update dependencies"
git push origin main
```

### Scale Celery Workers

```bash
# Edit docker-compose.yml
celery:
  deploy:
    replicas: 3  # Run 3 workers

# Deploy
docker-compose up -d --scale celery=3
```

### Monitor Performance

```bash
# Check resource usage
docker stats

# Check database size
docker-compose exec db psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('trading_bot'));"

# Check Redis memory
docker-compose exec redis redis-cli INFO memory
```

---

## Support

- **GitHub Issues**: [Your repo issues URL]
- **Documentation**: See [README.md](README.md)
- **Scripts Reference**: See [scripts/README.md](scripts/README.md)

---

**Last Updated**: 2025-11-10
