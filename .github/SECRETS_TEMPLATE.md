# GitHub Secrets Template

Copy this template when setting up GitHub Secrets for CI/CD deployment.

---

## Required Secrets

### Server Connection

```
SERVER_IP=YOUR_SERVER_IP
SERVER_USER=root
SSH_PRIVATE_KEY=<paste your private key here>
```

**How to get SSH_PRIVATE_KEY:**
```bash
# On your local machine
cat ~/.ssh/github_deploy_key

# Copy the ENTIRE output including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ... (all the lines)
# -----END OPENSSH PRIVATE KEY-----
```

---

### Docker Hub (NEW - Required for Image Registry)

```
DOCKER_USERNAME=yomeronepal
DOCKER_PASSWORD=<your_docker_hub_access_token>
```

**How to get Docker Hub Access Token:**
1. Go to [hub.docker.com](https://hub.docker.com)
2. Login or create account
3. Go to Account Settings → Security
4. Click "New Access Token"
5. Description: "GitHub Actions CI/CD"
6. Permissions: Read & Write
7. Copy the token (you won't see it again!)

---

### Application Configuration

```
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
DJANGO_SECRET_KEY=generate_with_command_below
DEBUG=False
ALLOWED_HOSTS=your-domain.com,192.168.1.100
```

**Generate Django Secret Key:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

### Optional Secrets (defaults provided)

If you want to customize database or Redis URLs:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db:5432/trading_bot
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

For frontend API URLs (if using custom domain):

```
REACT_APP_API_URL=https://api.your-domain.com
REACT_APP_WS_URL=wss://api.your-domain.com
```

---

## Setup Instructions

1. Go to your GitHub repository
2. Navigate to: **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret one by one:
   - Name: `SERVER_IP`
   - Value: `192.168.1.100` (your actual IP)
   - Click **Add secret**
5. Repeat for all required secrets above

---

## Verification

After adding secrets, verify in your repository:
- Settings → Secrets and variables → Actions
- You should see all secrets listed (values are hidden)

**Security Note:** GitHub Secrets are encrypted and never exposed in logs.

---

## Testing SSH Connection Locally

Before deploying, test your SSH key works:

```bash
# Test connection
ssh -i ~/.ssh/github_deploy_key root@YOUR_SERVER_IP

# If successful, you should be logged into your server
# If it asks for a password, the key is not configured correctly
```

---

## Common Issues

### "Permission denied (publickey)"
- Ensure you copied the PRIVATE key to GitHub Secrets (not public key)
- Verify the PUBLIC key is in server's `~/.ssh/authorized_keys`

### "Host key verification failed"
- This shouldn't happen because the workflow uses `StrictHostKeyChecking=no`
- If it does, check SERVER_IP is correct

### "Connection refused"
- Verify SERVER_IP is correct
- Check server firewall allows SSH (port 22)
- Ensure SSH service is running: `systemctl status sshd`

---

## Security Best Practices

1. **Rotate secrets regularly** - Update keys every 90 days
2. **Use read-only API keys** - For Binance, enable only necessary permissions
3. **Limit SSH access** - Use firewall rules to restrict IP addresses
4. **Monitor access logs** - Check `/var/log/auth.log` on server regularly
5. **Use strong passwords** - For database and Redis if exposed
6. **Enable 2FA** - On GitHub account and Binance account

---

## Next Steps

After setting up secrets:
1. Read [DEPLOYMENT.md](../DEPLOYMENT.md) for full deployment guide
2. Set up your server (install Docker, create directories)
3. Test deployment by pushing to `main` branch
4. Monitor deployment in Actions tab

---

**Last Updated**: 2025-11-10
