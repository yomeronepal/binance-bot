# CI/CD Quick Start Guide

Get automated deployment running in 15 minutes.

---

## Overview

This guide helps you set up automated deployment from GitHub to your server using GitHub Actions.

**What you'll get:**
- Push to `main` branch → Automatic deployment
- Zero-downtime deployments
- Automatic database backups
- Health checks after deployment

---

## Prerequisites

- A Linux server (Ubuntu 20.04+ recommended)
- SSH access (root or sudo user)
- GitHub repository
- 15 minutes

---

## Step 1: Generate SSH Key (2 minutes)

On your **local machine**:

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "github-actions-deploy"

# Save to: ~/.ssh/github_deploy_key (when prompted)
# No passphrase (just press Enter twice)
```

You now have:
- **Private key**: `~/.ssh/github_deploy_key` (keep secret!)
- **Public key**: `~/.ssh/github_deploy_key.pub` (share with server)

---

## Step 2: Setup Server (5 minutes)

### Option A: Automated Setup (Recommended)

Copy the setup script to your server and run it:

```bash
# Copy script to server
scp server-setup.sh root@YOUR_SERVER_IP:/tmp/

# SSH into server
ssh root@YOUR_SERVER_IP

# Run setup script
cd /tmp
chmod +x server-setup.sh
./server-setup.sh
```

### Option B: Manual Setup

```bash
# SSH into server
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Create directories
mkdir -p /opt/binance-bot
mkdir -p /opt/binance-bot-backups

# Install rsync (for file transfers)
apt install rsync -y
```

---

## Step 3: Configure SSH Access (2 minutes)

Add your public key to the server:

```bash
# On your local machine - copy public key content
cat ~/.ssh/github_deploy_key.pub

# Copy the output, then on your server
ssh root@YOUR_SERVER_IP
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys

# Paste your public key at the end
# Save and exit (Ctrl+X, Y, Enter)

# Set correct permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

**Test SSH connection:**

```bash
# On your local machine
ssh -i ~/.ssh/github_deploy_key root@YOUR_SERVER_IP

# If successful, you're logged in without password!
# Exit and continue
exit
```

---

## Step 4: Add GitHub Secrets (5 minutes)

### 4.1 Get Private Key Content

```bash
# On your local machine
cat ~/.ssh/github_deploy_key

# Copy EVERYTHING including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ... all the lines ...
# -----END OPENSSH PRIVATE KEY-----
```

### 4.2 Get Django Secret Key

```bash
# Generate a random secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Copy the output
```

### 4.3 Add Secrets to GitHub

1. Go to your GitHub repository
2. Click: **Settings** → **Secrets and variables** → **Actions**
3. Click: **New repository secret**
4. Add these secrets one by one:

| Name | Value | Example |
|------|-------|---------|
| `SERVER_IP` | Your server IP | `192.168.1.100` |
| `SERVER_USER` | SSH user | `root` |
| `SSH_PRIVATE_KEY` | Private key content | (paste entire key) |
| `BINANCE_API_KEY` | Your Binance API key | `abc123...` |
| `BINANCE_API_SECRET` | Your Binance secret | `xyz789...` |
| `DJANGO_SECRET_KEY` | Generated secret | (paste generated key) |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Server IP/domain | `192.168.1.100` |

**Optional secrets** (will use defaults if not provided):
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `REACT_APP_API_URL`

---

## Step 5: First Deployment (1 minute)

### Commit and Push

```bash
# On your local machine, in project directory
git add .
git commit -m "Add CI/CD pipeline"
git push origin main
```

### Watch Deployment

1. Go to GitHub repository
2. Click **Actions** tab
3. You'll see "Deploy to Production" workflow running
4. Click on it to watch live logs

**Expected timeline:**
- Test job: 1-2 minutes
- Deploy job: 3-5 minutes
- Total: ~5 minutes

---

## Step 6: Verify Deployment

### Check on GitHub

In the Actions tab, you should see:
- ✅ Test job completed
- ✅ Deploy job completed
- ✅ All steps green

### Check on Server

```bash
# SSH into server
ssh root@YOUR_SERVER_IP

# Check containers
cd /opt/binance-bot
docker-compose ps

# You should see:
# - web (running)
# - celery (running)
# - celery-beat (running)
# - db (running)
# - redis (running)

# Check logs
docker-compose logs --tail=50

# Test API
curl http://localhost:8000/api/health/

# Should return: {"status":"healthy","message":"Binance Trading Bot API is running"}
```

---

## Usage

### Deploy Changes

Just push to main:

```bash
git add .
git commit -m "Your changes"
git push origin main
```

GitHub Actions will automatically:
1. Run tests
2. Copy files to server
3. Build containers
4. Run migrations
5. Restart services
6. Verify health

### Manual Deployment

From GitHub Actions tab:
1. Click **Deploy to Production**
2. Click **Run workflow**
3. Select `main` branch
4. Click **Run workflow**

### View Logs

**On GitHub:**
- Actions tab → Click workflow → View logs

**On Server:**
```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f celery
```

---

## Common Issues

### "Permission denied (publickey)"

**Problem:** SSH key not configured correctly

**Solution:**
1. Verify you copied the **PRIVATE** key to GitHub Secrets (not public)
2. Verify the **PUBLIC** key is in server's `~/.ssh/authorized_keys`
3. Test locally: `ssh -i ~/.ssh/github_deploy_key root@YOUR_SERVER_IP`

### "No such file or directory: /opt/binance-bot"

**Problem:** Server not set up

**Solution:** Run `server-setup.sh` on server

### "Containers not starting"

**Problem:** Docker or Docker Compose not installed

**Solution:**
```bash
ssh root@YOUR_SERVER_IP
docker --version
docker-compose --version

# If missing, run server-setup.sh
```

### "Health check failed"

**Problem:** Services still starting or crashed

**Solution:**
```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Wait 30 seconds for services to start
sleep 30

# Check status
docker-compose ps

# Check logs for errors
docker-compose logs web
```

---

## Next Steps

### 1. Access Your Application

- **Frontend:** `http://YOUR_SERVER_IP:3000`
- **API:** `http://YOUR_SERVER_IP:8000/api/`
- **Admin:** `http://YOUR_SERVER_IP:8000/admin/`

### 2. Create Superuser

```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot
docker-compose exec web python manage.py createsuperuser
```

### 3. Download Historical Data

```bash
docker-compose exec web python scripts/data/download_long_period.py
```

### 4. Setup SSL (Recommended for Production)

```bash
# Install Certbot
apt install certbot python3-certbot-nginx -y

# Get certificate
certbot --nginx -d your-domain.com
```

### 5. Monitor Performance

```bash
# Resource usage
docker stats

# Database size
docker-compose exec db psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('trading_bot'));"
```

---

## Rollback

If something goes wrong:

```bash
# On your local machine
git revert HEAD
git push origin main

# GitHub Actions will deploy the previous version
```

---

## Documentation

- **Full Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Secrets Template:** [.github/SECRETS_TEMPLATE.md](.github/SECRETS_TEMPLATE.md)
- **Project README:** [README.md](README.md)

---

## Getting Help

- **GitHub Issues:** Check Actions tab for error logs
- **Server Logs:** `docker-compose logs` on server
- **Documentation:** See DEPLOYMENT.md for troubleshooting

---

## Checklist

Before going live:

- [ ] SSH key generated and configured
- [ ] Server setup complete (Docker installed)
- [ ] All GitHub Secrets added
- [ ] First deployment successful
- [ ] Health check passing
- [ ] Can access frontend and API
- [ ] Superuser created
- [ ] Historical data downloaded (optional)
- [ ] SSL certificate configured (recommended)
- [ ] Monitoring set up (optional)

---

**Congratulations!** 🎉

You now have automated CI/CD deployment. Every push to `main` will automatically update your production server.

---

**Last Updated**: 2025-11-10
