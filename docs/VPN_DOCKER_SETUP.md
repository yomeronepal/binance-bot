# Docker VPN Setup - Free Options

## Problem
Binance API requires VPN in some regions, but you don't want VPN running on your entire system.

## Solution
Route only Docker containers through VPN using **Gluetun** - a lightweight VPN container.

---

## Free VPN Options (Ranked)

### 1. ProtonVPN Free ⭐ RECOMMENDED
- **Data**: Unlimited
- **Speed**: Medium (free tier throttled)
- **Servers**: Netherlands, USA, Japan
- **Setup**: Use existing ProtonVPN credentials
- **Sign up**: https://account.protonvpn.com/signup

**Pros**: Unlimited data, reputable company, no logs
**Cons**: Limited server choice, slower speeds

### 2. Windscribe Free
- **Data**: 10 GB/month (15GB with email confirmation)
- **Speed**: Fast
- **Servers**: 10 countries
- **Sign up**: https://windscribe.com/signup

**Pros**: Fast speeds, good for testing
**Cons**: 10GB monthly limit

### 3. Hide.me Free
- **Data**: 10 GB/month
- **Speed**: Fast
- **Servers**: 5 locations
- **Sign up**: https://hide.me/en/pricing

**Pros**: No logs, fast
**Cons**: 10GB limit

---

## Quick Setup (ProtonVPN Free)

### Step 1: Get ProtonVPN Free Credentials
1. Sign up: https://account.protonvpn.com/signup
2. Verify email
3. Note your **OpenVPN/IKEv2 username** and **password**
   - Find at: Account → OpenVPN/IKEv2 credentials
   - Username looks like: `your-email+f1`
   - NOT your regular login credentials!

### Step 2: Create `.env.vpn` File
```bash
# Copy the example file
cp .env.vpn.example .env.vpn

# Edit with your credentials
PROTONVPN_USERNAME=your-email+f1
PROTONVPN_PASSWORD=your-openvpn-password
```

### Step 3: Stop Current Containers
```bash
docker-compose down
```

### Step 4: Start with VPN
```bash
# Load VPN environment variables
docker-compose --env-file .env.vpn -f docker-compose-with-vpn.yml up -d
```

### Step 5: Verify VPN is Working
```bash
# Check VPN container logs
docker logs binance-bot-vpn

# Should see:
# ✓ [INFO] VPN is up
# ✓ [INFO] Connected to ProtonVPN

# Test external IP (should show VPN IP, not your real IP)
docker exec binance-bot-backend curl -s https://api.ipify.org
```

---

## Architecture

### Before (No VPN)
```
Your PC → Internet → Binance API
         (Your real IP exposed)
```

### After (Docker VPN)
```
Your PC → Docker Network → VPN Container → Internet → Binance API
         (VPN IP shown)

Other apps on your PC → Direct Internet
                        (No VPN)
```

**Key**: Only Docker containers use VPN, your PC's other apps use normal connection.

---

## How It Works

### docker-compose-with-vpn.yml Key Changes

1. **VPN Container**:
```yaml
vpn:
  image: qmcgaw/gluetun:latest
  cap_add:
    - NET_ADMIN  # Required for VPN routing
  environment:
    - VPN_SERVICE_PROVIDER=protonvpn
    - OPENVPN_USER=${PROTONVPN_USERNAME}
    - OPENVPN_PASSWORD=${PROTONVPN_PASSWORD}
  ports:
    - "8000:8000"  # Expose app ports through VPN
```

2. **Containers Route Through VPN**:
```yaml
backend:
  network_mode: "service:vpn"  # Route ALL traffic through VPN

celery-worker:
  network_mode: "service:vpn"  # Binance API calls go through VPN
```

3. **Database/Redis Stay Local** (no VPN needed):
```yaml
db:
  networks:
    - binance-network  # Normal network, no VPN
```

---

## Troubleshooting

### Issue: VPN container fails to start
```bash
# Check logs
docker logs binance-bot-vpn

# Common causes:
# 1. Wrong credentials
# 2. Free servers full (try different country)
# 3. Port conflicts
```

**Fix**:
```bash
# Try different server
# Edit docker-compose-with-vpn.yml:
- SERVER_COUNTRIES=United States  # Instead of Netherlands
```

### Issue: Containers can't reach database
```bash
# Symptom: "connection refused" errors

# Cause: Database needs to be accessible from VPN network

# Fix: Ensure DB has its own network, not routed through VPN
```

### Issue: Backend/Celery can't start
```bash
# Check if VPN is up first
docker logs binance-bot-vpn | grep "VPN is up"

# If not up, wait 30 seconds for VPN to connect
# Then restart dependent containers
docker restart binance-bot-backend binance-bot-celery-worker
```

### Issue: Slow backtest performance
```bash
# ProtonVPN free tier is throttled
# Solutions:
# 1. Use Windscribe (faster but 10GB limit)
# 2. Run backtests at night (less congestion)
# 3. Upgrade to ProtonVPN Plus (paid)
```

---

## Alternative: Windscribe Free Setup

If ProtonVPN is too slow, try Windscribe (10GB/month but faster):

### Step 1: Sign Up
1. https://windscribe.com/signup
2. Verify email to get 10GB → 15GB

### Step 2: Get OpenVPN Credentials
1. Login → My Account
2. Scroll to "OpenVPN Config Generator"
3. Note **Username** and **Password**

### Step 3: Update docker-compose-with-vpn.yml
```yaml
vpn:
  environment:
    - VPN_SERVICE_PROVIDER=windscribe
    - OPENVPN_USER=${WINDSCRIBE_USERNAME}
    - OPENVPN_PASSWORD=${WINDSCRIBE_PASSWORD}
    - SERVER_COUNTRIES=Netherlands  # Or any Windscribe location
```

### Step 4: Update .env.vpn
```bash
WINDSCRIBE_USERNAME=your-username
WINDSCRIBE_PASSWORD=your-password
```

### Step 5: Start
```bash
docker-compose --env-file .env.vpn -f docker-compose-with-vpn.yml up -d
```

---

## Performance Comparison

| VPN Provider | Speed | Data Limit | Best For |
|--------------|-------|------------|----------|
| ProtonVPN Free | Slow-Medium | Unlimited | Long backtests (1000+ combos) |
| Windscribe Free | Fast | 10-15 GB/month | Testing, short sweeps |
| Hide.me Free | Fast | 10 GB/month | Occasional use |
| Your Proton Plus | Fast | Unlimited | Production ⭐ |

**Recommendation for 1539 backtest sweep**:
- ProtonVPN Free (unlimited data, can take 5-6 hours)
- Or Windscribe (faster, 3-4 hours, but watch data usage)

---

## Monitoring VPN Usage

### Check VPN Status
```bash
# Is VPN connected?
docker logs binance-bot-vpn | grep "VPN is up"

# What's my VPN IP?
docker exec binance-bot-backend curl -s https://api.ipify.org

# Test Binance API access
docker exec binance-bot-backend curl -s https://api.binance.com/api/v3/ping
# Should return: {}
```

### Monitor Data Usage (Windscribe/Hide.me)
```bash
# Check data usage on provider website
# Windscribe: Account page shows remaining GB
# Hide.me: Account dashboard
```

---

## Switching Back to Your VPN

When you're done with backtests and want to use your Proton Plus again:

```bash
# Stop VPN containers
docker-compose -f docker-compose-with-vpn.yml down

# Start regular containers (no VPN routing)
docker-compose up -d

# Turn on Proton VPN on your PC
# Now your PC uses VPN, Docker doesn't
```

---

## Production Recommendation

**For live trading**: Use your existing Proton Plus VPN on your PC
- More reliable
- Faster speeds
- Better security

**For backtesting**: Use Docker VPN (ProtonVPN Free)
- Keep VPN off on your PC
- Only Docker uses VPN
- Saves your Proton Plus connection for important stuff

---

## Security Notes

1. **Never commit .env.vpn** - Already in .gitignore
2. **Use OpenVPN credentials** - Not your account password
3. **Free VPNs log less** - ProtonVPN has strict no-logs policy
4. **VPN container isolated** - Can't access your PC's filesystem

---

## Quick Commands Reference

```bash
# Start with VPN
docker-compose --env-file .env.vpn -f docker-compose-with-vpn.yml up -d

# Stop
docker-compose -f docker-compose-with-vpn.yml down

# Check VPN status
docker logs binance-bot-vpn | tail -20

# Restart VPN (if connection drops)
docker restart binance-bot-vpn

# Check external IP
docker exec binance-bot-backend curl -s https://api.ipify.org

# Monitor backtest progress
docker logs binance-bot-celery-worker --follow

# Switch back to normal (no VPN)
docker-compose -f docker-compose-with-vpn.yml down
docker-compose up -d
```

---

## Cost Comparison

| Solution | Cost | Data | Speed | Setup Time |
|----------|------|------|-------|------------|
| Proton Plus (current) | $5-10/mo | Unlimited | Fast | 0 min (already have) |
| ProtonVPN Free | $0 | Unlimited | Slow | 5 min setup |
| Windscribe Free | $0 | 10-15 GB | Fast | 5 min setup |
| Docker VPN + Proton Plus | $5-10/mo | Unlimited | Fast (hybrid) | 10 min setup |

**Best Setup** (Recommended):
- **PC**: Proton Plus (for browsing, live trading)
- **Docker**: ProtonVPN Free (for backtesting only)
- **Result**: Free backtesting, premium experience for everything else

---

## Next Steps

1. ✅ Sign up for ProtonVPN Free (if not already)
2. ✅ Create `.env.vpn` with OpenVPN credentials
3. ✅ Stop current containers
4. ✅ Start with VPN: `docker-compose --env-file .env.vpn -f docker-compose-with-vpn.yml up -d`
5. ✅ Verify VPN: `docker logs binance-bot-vpn`
6. ✅ Test Binance API: `docker exec binance-bot-backend curl https://api.binance.com/api/v3/ping`
7. ✅ Resume backtest sweep

Estimated setup time: **10 minutes**
Estimated backtest time with ProtonVPN Free: **4-6 hours**

---

## FAQ

**Q: Will this slow down my PC?**
A: No, only Docker uses VPN. Your PC's regular connection is unaffected.

**Q: Can I use this for live trading?**
A: Yes, but your Proton Plus is faster. This is better for backtesting.

**Q: What if VPN disconnects during backtest?**
A: Gluetun auto-reconnects. Backtests will resume once VPN is back.

**Q: Is ProtonVPN Free really unlimited?**
A: Yes, but throttled speeds. Perfect for backtests (data heavy, not speed sensitive).

**Q: Does this work on Windows?**
A: Yes! Docker Desktop on Windows fully supports this setup.

---

**Status**: ✅ Ready to implement
**Difficulty**: Easy (10 min setup)
**Cost**: Free (ProtonVPN Free or Windscribe Free)
**Benefit**: Docker uses VPN, your PC doesn't
