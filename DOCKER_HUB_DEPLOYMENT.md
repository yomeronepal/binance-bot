# Docker Hub Deployment Guide

This guide explains the Docker Hub-based CI/CD pipeline for the Binance Trading Bot.

---

## Overview

The deployment workflow now:
1. **Builds** Docker images on GitHub Actions
2. **Pushes** images to Docker Hub (`yomeronepal/binance-bot`)
3. **Pulls** pre-built images on your server
4. **Deploys** using `docker-compose.prod.yml`

**Benefits:**
- Faster deployments (no building on server)
- Consistent images across environments
- Better caching and layer reuse
- Easier rollback to previous versions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Developer Push                           │
│                    git push origin main                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Actions Workflow                     │
├─────────────────────────────────────────────────────────────┤
│  JOB 1: Test                                                 │
│  └─ Run syntax checks and linting                           │
│                                                              │
│  JOB 2: Build & Push                                         │
│  ├─ Build backend image                                     │
│  ├─ Build frontend image                                    │
│  ├─ Tag: backend-{sha}-{timestamp}                          │
│  ├─ Tag: backend-latest                                     │
│  ├─ Push to yomeronepal/binance-bot:backend-latest          │
│  └─ Push to yomeronepal/binance-bot:frontend-latest         │
│                                                              │
│  JOB 3: Deploy                                               │
│  ├─ Copy files to server                                    │
│  ├─ SSH into server                                         │
│  └─ Run deploy.sh                                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Docker Hub Registry                        │
│              hub.docker.com/u/yomeronepal                    │
├─────────────────────────────────────────────────────────────┤
│  Images:                                                     │
│  ├─ binance-bot:backend-latest                              │
│  ├─ binance-bot:backend-abc123-20250110                     │
│  ├─ binance-bot:frontend-latest                             │
│  └─ binance-bot:frontend-abc123-20250110                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Production Server                         │
│                   /opt/binance-bot/                          │
├─────────────────────────────────────────────────────────────┤
│  deploy.sh:                                                  │
│  ├─ docker-compose -f docker-compose.prod.yml pull          │
│  ├─ docker-compose -f docker-compose.prod.yml up -d         │
│  └─ Run migrations                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Setup Instructions

### Step 1: Create Docker Hub Account

1. Go to [hub.docker.com](https://hub.docker.com)
2. Sign up or log in
3. Your username: `yomeronepal` (already configured)

### Step 2: Create Access Token

1. Go to [Account Settings → Security](https://hub.docker.com/settings/security)
2. Click **New Access Token**
3. Description: `GitHub Actions CI/CD`
4. Access permissions: **Read & Write**
5. Click **Generate**
6. **Copy the token** (you won't see it again!)

### Step 3: Add Docker Hub Secrets to GitHub

Go to your GitHub repository:
**Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets:

| Secret Name | Value |
|-------------|-------|
| `DOCKER_USERNAME` | `yomeronepal` |
| `DOCKER_PASSWORD` | Your access token from Step 2 |

### Step 4: Verify GitHub Secrets

You should now have these secrets configured:

**Server Connection:**
- `SERVER_IP`
- `SERVER_USER`
- `SSH_PRIVATE_KEY`

**Application:**
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `DJANGO_SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`

**Docker Hub (NEW):**
- `DOCKER_USERNAME`
- `DOCKER_PASSWORD`

---

## How It Works

### Image Tagging Strategy

Each build creates two tags:

1. **Version-specific tag**: `backend-{git-sha}-{timestamp}`
   - Example: `backend-abc123-20250110-143022`
   - Permanent, for rollback

2. **Latest tag**: `backend-latest`
   - Always points to most recent build
   - Used for production deployment

### Docker Images

**Backend Image:**
- Repository: `yomeronepal/binance-bot`
- Tags: `backend-latest`, `backend-{sha}-{timestamp}`
- Based on: Python 3.11
- Contains: Django app, Celery workers
- Used by: `web`, `celery`, `celery-beat` containers

**Frontend Image:**
- Repository: `yomeronepal/binance-bot`
- Tags: `frontend-latest`, `frontend-{sha}-{timestamp}`
- Based on: Node.js
- Contains: React/Vite app
- Used by: `frontend` container

### File: docker-compose.prod.yml

Production-specific compose file that:
- Uses pre-built images from Docker Hub
- Adds `restart: unless-stopped` for reliability
- Mounts only necessary volumes (no source code)
- Optimized for production use

**Key differences from dev compose:**

| Feature | Development | Production |
|---------|-------------|------------|
| Images | Build locally | Pull from Docker Hub |
| Code volumes | Mounted (live reload) | Not mounted (baked in image) |
| Restart policy | No | `unless-stopped` |
| Compose file | `docker-compose.yml` | `docker-compose.prod.yml` |

---

## Deployment Workflow

### Automatic Deployment

```bash
# Make changes
git add .
git commit -m "Your changes"
git push origin main
```

**What happens:**
1. GitHub Actions runs tests (2 min)
2. Builds Docker images (3-5 min)
3. Pushes to Docker Hub (1 min)
4. Deploys to server (2-3 min)
5. **Total: ~8-10 minutes**

### Manual Deployment

**From GitHub UI:**
1. Go to Actions tab
2. Click "Deploy to Production"
3. Click "Run workflow"
4. Select `main` branch

**From Server (emergency):**
```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot
./deploy.sh
```

---

## Monitoring

### View Build Progress

**On GitHub:**
1. Go to Actions tab
2. Click running workflow
3. Expand "Build and Push Docker Images" job
4. Watch build logs in real-time

### View Images on Docker Hub

1. Go to [hub.docker.com/r/yomeronepal/binance-bot](https://hub.docker.com/r/yomeronepal/binance-bot)
2. See all pushed images
3. Check tags and timestamps
4. View image sizes and layers

### View Deployment on Server

```bash
# SSH into server
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# View containers
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# View specific service
docker-compose -f docker-compose.prod.yml logs -f web
```

---

## Rollback Procedures

### Option 1: Git Revert (Recommended)

```bash
# On local machine
git revert HEAD
git push origin main

# Automatically triggers new build and deployment with previous code
```

### Option 2: Pull Specific Image Tag

```bash
# SSH into server
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Edit docker-compose.prod.yml
nano docker-compose.prod.yml

# Change:
# image: yomeronepal/binance-bot:backend-latest
# To:
# image: yomeronepal/binance-bot:backend-abc123-20250110-143022

# Redeploy
./deploy.sh
```

### Option 3: Manual Restore

```bash
# SSH into server
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Restore database
docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres trading_bot < /opt/binance-bot-backups/db_backup_TIMESTAMP.sql

# Checkout previous commit
git log --oneline
git checkout PREVIOUS_COMMIT_HASH

# Pull old images (if available)
docker pull yomeronepal/binance-bot:backend-PREVIOUS_TAG

# Redeploy
./deploy.sh
```

---

## Commands Reference

### Local Development (uses docker-compose.yml)

```bash
# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild
docker-compose build --no-cache
```

### Production (uses docker-compose.prod.yml)

```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart service
docker-compose -f docker-compose.prod.yml restart web

# Stop all
docker-compose -f docker-compose.prod.yml down

# Remove volumes (WARNING: deletes data)
docker-compose -f docker-compose.prod.yml down -v
```

### Docker Hub Commands

```bash
# Login to Docker Hub
docker login -u yomeronepal

# Pull image
docker pull yomeronepal/binance-bot:backend-latest

# List local images
docker images | grep binance-bot

# Remove old images
docker image prune -a

# View image history
docker history yomeronepal/binance-bot:backend-latest
```

---

## Troubleshooting

### Build Fails: "Authentication required"

**Problem:** Docker Hub credentials not configured

**Solution:**
1. Verify `DOCKER_USERNAME` and `DOCKER_PASSWORD` in GitHub Secrets
2. Ensure password is an access token (not account password)
3. Check token has "Read & Write" permissions

### Push Fails: "denied: requested access to the resource is denied"

**Problem:** No permission to push to repository

**Solution:**
1. Verify repository exists: `yomeronepal/binance-bot`
2. Check you're logged in: `docker login`
3. Ensure token has write permissions

### Server Can't Pull Images: "pull access denied"

**Problem:** Image is private or doesn't exist

**Solution:**
```bash
# Check if image exists on Docker Hub
docker pull yomeronepal/binance-bot:backend-latest

# If it's private, login on server
docker login -u yomeronepal

# Then pull
docker-compose -f docker-compose.prod.yml pull
```

### Containers Using Old Images

**Problem:** Server has cached old images

**Solution:**
```bash
# Force pull new images
docker-compose -f docker-compose.prod.yml pull

# Remove old images
docker image prune -a -f

# Restart
docker-compose -f docker-compose.prod.yml up -d
```

### Build Takes Too Long

**Problem:** No cache, rebuilding from scratch

**Solution:**
- GitHub Actions uses layer caching (already configured)
- First build: ~5-8 minutes
- Subsequent builds: ~2-3 minutes

### Images Too Large

**Current sizes:**
- Backend: ~500-800 MB
- Frontend: ~300-500 MB

**To reduce:**
1. Use multi-stage builds (already done)
2. Use alpine base images (already done)
3. Minimize dependencies in requirements.txt
4. Add `.dockerignore` file

---

## Advanced Configuration

### Multi-Stage Build Optimization

Already configured in Dockerfile:
```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder
# Install dependencies

# Stage 2: Runtime
FROM python:3.11-slim
# Copy only necessary files
```

### Build Cache Configuration

Already configured in workflow:
```yaml
cache-from: type=registry,ref=yomeronepal/binance-bot:backend-buildcache
cache-to: type=registry,ref=yomeronepal/binance-bot:backend-buildcache,mode=max
```

### Custom Image Tags

Edit `.github/workflows/deploy.yml`:
```yaml
tags: |
  yomeronepal/binance-bot:backend-v1.0.0
  yomeronepal/binance-bot:backend-${{ github.ref_name }}
```

### Deploy to Multiple Environments

Create separate compose files:
- `docker-compose.staging.yml`
- `docker-compose.prod.yml`

Update workflow to deploy based on branch:
```yaml
on:
  push:
    branches:
      - main        # Production
      - staging     # Staging
```

---

## Security Best Practices

1. **Never commit Docker Hub credentials**
   - Always use GitHub Secrets
   - Use access tokens (not passwords)

2. **Rotate access tokens regularly**
   - Recommended: Every 90 days
   - Revoke old tokens after rotation

3. **Use minimal base images**
   - Already using `python:3.11-slim` and `alpine`
   - Reduces attack surface

4. **Scan images for vulnerabilities**
   ```bash
   docker scan yomeronepal/binance-bot:backend-latest
   ```

5. **Use read-only filesystem where possible**
   ```yaml
   services:
     web:
       read_only: true
       tmpfs:
         - /tmp
   ```

6. **Limit image retention**
   - Delete old images from Docker Hub after 30 days
   - Keep last 10 versions for rollback

---

## Cost Optimization

### Docker Hub Free Tier

- **Pulls:** Unlimited
- **Storage:** Unlimited
- **Retention:** 6 months inactivity
- **Bandwidth:** Fair use

### GitHub Actions Free Tier

- **Minutes:** 2,000/month for private repos
- **Storage:** 500 MB
- **Concurrent jobs:** 20

**Current usage:**
- ~10 minutes per deployment
- ~200 deployments/month possible

### Tips to Reduce Costs

1. **Use cache effectively** (already configured)
2. **Only build changed images**
3. **Use smaller base images** (already done)
4. **Clean up old images regularly**

---

## Maintenance

### Regular Tasks

**Weekly:**
- Check Docker Hub for old images
- Review deployment logs
- Monitor image sizes

**Monthly:**
- Rotate Docker Hub access tokens
- Update base images
- Clean up old backups on server

**Quarterly:**
- Review and optimize Dockerfiles
- Update dependencies
- Security audit of images

### Cleanup Commands

```bash
# On server - clean old images
docker image prune -a -f

# On server - clean old containers
docker container prune -f

# On server - clean old volumes (CAREFUL!)
docker volume prune -f

# On server - full cleanup
docker system prune -a --volumes -f
```

---

## Comparison: Before vs After

| Aspect | Before (Build on Server) | After (Docker Hub) |
|--------|-------------------------|-------------------|
| Deployment time | 5-7 minutes | 2-3 minutes |
| Server load | High (building) | Low (pulling) |
| Consistency | May vary | 100% consistent |
| Rollback | Git checkout + rebuild | Pull old image |
| Caching | Local only | Shared via registry |
| Build failures | Block server | Detected early |
| Multi-server | Rebuild each | Pull same image |

---

## Next Steps

1. ✅ Docker Hub account created
2. ✅ Access token generated
3. ✅ GitHub Secrets configured
4. ✅ Workflow updated
5. ✅ Production compose file created
6. ⏳ Test first deployment
7. ⏳ Monitor Docker Hub images
8. ⏳ Setup image retention policy

---

## Resources

- **Docker Hub**: [hub.docker.com/r/yomeronepal/binance-bot](https://hub.docker.com/r/yomeronepal/binance-bot)
- **GitHub Actions**: Repository → Actions tab
- **Documentation**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Quick Start**: [CICD_QUICKSTART.md](CICD_QUICKSTART.md)

---

**Last Updated**: 2025-11-10
