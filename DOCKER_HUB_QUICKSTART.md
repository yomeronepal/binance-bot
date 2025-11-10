# Docker Hub Deployment - Quick Start

Get Docker Hub-based deployment running in 10 minutes.

---

## What Changed?

Instead of building Docker images on your server (slow), we now:
1. **Build** images on GitHub Actions
2. **Push** to Docker Hub (`yomeronepal/binance-bot`)
3. **Pull** pre-built images on your server

**Result:** Faster deployments (3 min vs 7 min), consistent images, easier rollback.

---

## Setup Steps

### 1. Create Docker Hub Access Token (2 minutes)

1. Go to [hub.docker.com](https://hub.docker.com)
2. Login (or create account)
3. Go to: **Account Settings → Security**
4. Click **New Access Token**
5. Settings:
   - Description: `GitHub Actions CI/CD`
   - Permissions: **Read & Write**
6. Click **Generate**
7. **Copy the token** (you won't see it again!)

### 2. Add Docker Hub Secrets to GitHub (2 minutes)

Go to your repository: **Settings → Secrets and variables → Actions**

Add **2 new secrets**:

| Secret Name | Value |
|-------------|-------|
| `DOCKER_USERNAME` | `yomeronepal` |
| `DOCKER_PASSWORD` | Paste your access token from step 1 |

### 3. Verify All Secrets (1 minute)

You should now have these secrets:

**Required:**
- ✅ `SERVER_IP`
- ✅ `SERVER_USER`
- ✅ `SSH_PRIVATE_KEY`
- ✅ `DOCKER_USERNAME` ← NEW
- ✅ `DOCKER_PASSWORD` ← NEW
- ✅ `BINANCE_API_KEY`
- ✅ `BINANCE_API_SECRET`
- ✅ `DJANGO_SECRET_KEY`
- ✅ `DEBUG`
- ✅ `ALLOWED_HOSTS`

### 4. Update Server Files (3 minutes)

The new files are already in your repo. Just deploy them:

```bash
# Commit and push the changes
git add .
git commit -m "Add Docker Hub deployment"
git push origin main
```

**What happens:**
1. GitHub Actions builds images (~5 min first time)
2. Pushes to Docker Hub (~1 min)
3. Deploys to server using `docker-compose.prod.yml` (~2 min)
4. **Total: ~8 minutes first time, 3-4 min after**

### 5. Monitor Deployment (2 minutes)

**On GitHub:**
1. Go to **Actions** tab
2. Click running workflow
3. Watch the build progress

**On Docker Hub:**
1. Go to [hub.docker.com/r/yomeronepal/binance-bot](https://hub.docker.com/r/yomeronepal/binance-bot)
2. See your images appear:
   - `backend-latest`
   - `frontend-latest`

**On Server:**
```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Check containers are running
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f web
```

---

## New Files Overview

| File | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production compose using Docker Hub images |
| `deploy.sh` (updated) | Now pulls images instead of building |
| `.github/workflows/deploy.yml` (updated) | Builds and pushes to Docker Hub |
| `DOCKER_HUB_DEPLOYMENT.md` | Full documentation |
| `DOCKER_HUB_QUICKSTART.md` | This file |

---

## Usage

### Deploy (Same as Before!)

```bash
git add .
git commit -m "Your changes"
git push origin main
```

**Now faster:** 3-4 min (was 5-7 min)

### View Images

**On Docker Hub:**
```
https://hub.docker.com/r/yomeronepal/binance-bot/tags
```

**On Server:**
```bash
docker images | grep binance-bot
```

### Rollback

**Option 1: Git revert (easiest)**
```bash
git revert HEAD
git push origin main
```

**Option 2: Use old image tag**
```bash
# SSH to server
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Edit docker-compose.prod.yml
nano docker-compose.prod.yml

# Change: backend-latest
# To: backend-abc123-20250110-143022

# Redeploy
./deploy.sh
```

---

## Troubleshooting

### "Authentication required" during build

**Problem:** Docker Hub credentials not configured

**Fix:**
1. Verify `DOCKER_USERNAME` = `yomeronepal` in GitHub Secrets
2. Verify `DOCKER_PASSWORD` = your access token (not account password!)
3. Check token has "Read & Write" permissions

### Can't find images on Docker Hub

**Problem:** First push hasn't completed yet

**Fix:**
1. Wait for GitHub Actions workflow to complete
2. Check Actions tab for errors
3. Verify workflow reached "Build and Push Docker Images" job

### Server can't pull images

**Problem:** Images are private or don't exist

**Fix:**
```bash
# Login to Docker Hub on server (one-time)
ssh root@YOUR_SERVER_IP
docker login -u yomeronepal

# Enter your Docker Hub password when prompted
# Then redeploy
cd /opt/binance-bot
./deploy.sh
```

### Containers using old images

**Problem:** Docker cached old images

**Fix:**
```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot

# Force pull new images
docker-compose -f docker-compose.prod.yml pull

# Remove old images
docker image prune -a -f

# Restart
docker-compose -f docker-compose.prod.yml up -d
```

---

## Benefits Summary

| Before | After |
|--------|-------|
| Build on server (slow) | Pull pre-built images (fast) |
| 5-7 min deployment | 3-4 min deployment |
| Server load high | Server load low |
| Inconsistent builds | 100% consistent |
| Hard to rollback | Easy rollback (pull old tag) |
| No build cache | Cached builds |

---

## Image Tags Explained

Each deployment creates **2 tags**:

1. **`backend-latest`** - Always newest version (used for production)
2. **`backend-abc123-20250110`** - Specific version (for rollback)

Example on Docker Hub:
```
yomeronepal/binance-bot:backend-latest
yomeronepal/binance-bot:backend-abc123-20250110-143022
yomeronepal/binance-bot:backend-def456-20250109-120000
yomeronepal/binance-bot:frontend-latest
yomeronepal/binance-bot:frontend-abc123-20250110-143022
```

---

## Commands

### Production Commands (Updated!)

```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart a service
docker-compose -f docker-compose.prod.yml restart web

# View status
docker-compose -f docker-compose.prod.yml ps

# Stop all
docker-compose -f docker-compose.prod.yml down
```

### Development Commands (Unchanged)

```bash
# Build and start (local dev)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## Next Steps

1. ✅ Add `DOCKER_USERNAME` and `DOCKER_PASSWORD` to GitHub Secrets
2. ✅ Push changes to trigger first build
3. ⏳ Wait for images to build and push (~8 min)
4. ⏳ Verify images on Docker Hub
5. ⏳ Check deployment on server
6. ⏳ Test rollback procedure

---

## Documentation

- **Full Guide:** [DOCKER_HUB_DEPLOYMENT.md](DOCKER_HUB_DEPLOYMENT.md)
- **Original Setup:** [CICD_QUICKSTART.md](CICD_QUICKSTART.md)
- **Secrets Template:** [.github/SECRETS_TEMPLATE.md](.github/SECRETS_TEMPLATE.md)

---

## Support

**If something goes wrong:**
1. Check GitHub Actions logs (Actions tab)
2. Check Docker Hub for images
3. SSH to server and check logs
4. Read [DOCKER_HUB_DEPLOYMENT.md](DOCKER_HUB_DEPLOYMENT.md) for detailed troubleshooting

---

**You're all set!** Push to `main` and watch your images build and deploy automatically.

---

**Last Updated**: 2025-11-10
