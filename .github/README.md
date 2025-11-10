# GitHub Actions CI/CD

This directory contains GitHub Actions workflows for automated deployment.

---

## Files

- **workflows/deploy.yml** - Main deployment workflow
- **SECRETS_TEMPLATE.md** - Template for required GitHub Secrets

---

## Quick Start

1. **Setup GitHub Secrets**
   - Go to: Repository → Settings → Secrets and variables → Actions
   - Add all secrets from [SECRETS_TEMPLATE.md](SECRETS_TEMPLATE.md)

2. **Setup Server**
   - Run [server-setup.sh](../server-setup.sh) on your server
   - Configure SSH access

3. **Deploy**
   - Push to `main` branch
   - Or manually trigger from Actions tab

---

## Workflow Overview

### Deploy to Production

**Trigger:** Push to `main` or manual trigger

**Jobs:**
1. **test** - Runs syntax checks and linting
2. **deploy** - Deploys to production server
3. **notify** - Sends deployment status notification

**Steps:**
1. Checkout code
2. Create .env files from secrets
3. Setup SSH connection
4. Copy files to server via rsync
5. Run deployment script on server
6. Verify deployment health

---

## Required Secrets

### Minimal Setup

```
SERVER_IP=192.168.1.100
SERVER_USER=root
SSH_PRIVATE_KEY=<your-private-key>
BINANCE_API_KEY=<your-key>
BINANCE_API_SECRET=<your-secret>
DJANGO_SECRET_KEY=<generate-random-key>
```

See [SECRETS_TEMPLATE.md](SECRETS_TEMPLATE.md) for complete list.

---

## Customization

### Add Staging Environment

Create `workflows/deploy-staging.yml`:

```yaml
name: Deploy to Staging

on:
  push:
    branches:
      - develop

jobs:
  deploy:
    # Use staging secrets: SERVER_IP_STAGING, etc.
```

### Add Slack Notifications

Add to workflow:

```yaml
- name: Notify Slack
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Add More Tests

Edit the `test` job in `deploy.yml`:

```yaml
- name: Run Django Tests
  run: |
    cd backend
    python manage.py test

- name: Run Frontend Tests
  run: |
    cd client
    npm install
    npm test
```

---

## Monitoring

### View Deployment Logs

**On GitHub:**
1. Go to Actions tab
2. Click on latest workflow run
3. View live logs

**On Server:**
```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot
docker-compose logs -f
```

---

## Troubleshooting

### Deployment Fails

1. Check workflow logs in Actions tab
2. SSH into server and check logs:
   ```bash
   cd /opt/binance-bot
   docker-compose logs
   ```

### Common Issues

**Permission Denied (SSH)**
- Verify SSH_PRIVATE_KEY is correct in GitHub Secrets
- Check server has public key in ~/.ssh/authorized_keys

**Build Fails**
- Check Docker logs: `docker-compose logs`
- Verify .env files are correct
- Check disk space: `df -h`

**Health Check Fails**
- Wait 30 seconds for services to start
- Check container status: `docker-compose ps`
- View web logs: `docker-compose logs web`

---

## Rollback

### Via Git

```bash
git revert HEAD
git push origin main
```

### Manual on Server

```bash
ssh root@YOUR_SERVER_IP
cd /opt/binance-bot
git log --oneline
git checkout PREVIOUS_COMMIT_HASH
./deploy.sh
```

---

## Security

- Secrets are encrypted by GitHub
- Never commit secrets to repository
- Rotate SSH keys regularly
- Use principle of least privilege
- Monitor access logs

---

## Documentation

- [DEPLOYMENT.md](../DEPLOYMENT.md) - Full deployment guide
- [SECRETS_TEMPLATE.md](SECRETS_TEMPLATE.md) - Secrets reference
- [README.md](../README.md) - Project overview

---

**Last Updated**: 2025-11-10
