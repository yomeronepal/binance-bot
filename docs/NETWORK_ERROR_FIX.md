# Network Connectivity Error - Fixed

**Date**: November 8, 2025
**Issue**: DNS Resolution Failure (`socket.gaierror: [Errno -3] Temporary failure in name resolution`)
**Status**: ✅ Fixed with enhanced error handling

---

## 🔴 Original Error

```
[2025-11-08 09:12:02,610: ERROR/ForkPoolWorker-11] ❌ Error in market scan:
Cannot connect to host api.binance.com:443 ssl:default
[Temporary failure in name resolution]

socket.gaierror: [Errno -3] Temporary failure in name resolution
```

**Root Cause**: DNS resolution failure - Docker container cannot resolve `api.binance.com` hostname.

---

## ✅ Fixes Applied

### 1. Enhanced Error Handling in BinanceClient

**File**: [backend/scanner/services/binance_client.py](../backend/scanner/services/binance_client.py)

**Changes**:
- ✅ Added specific handling for `socket.gaierror` (DNS failures)
- ✅ Added handling for connection timeouts and network errors
- ✅ Implemented exponential backoff (2s → 4s → 8s → 16s → 32s → 60s max)
- ✅ Increased retry attempts from 3 to 5
- ✅ Added descriptive error messages with troubleshooting hints
- ✅ Improved connection pooling with DNS caching

**Before**:
```python
except aiohttp.ClientError as e:
    logger.error(f"Request failed: {e}")
    if attempt == retries - 1:
        raise
    await asyncio.sleep(backoff)
```

**After**:
```python
except socket.gaierror as e:
    # DNS resolution failure
    backoff = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
    logger.error(
        f"🌐 DNS resolution failed for {self.BASE_URL}: {e}\n"
        f"   Attempt {attempt + 1}/{MAX_RETRIES}. Retrying in {backoff}s...\n"
        f"   This usually means: No internet connection or DNS server unavailable"
    )
    if attempt == MAX_RETRIES - 1:
        raise ConnectionError(
            f"Cannot resolve {self.BASE_URL} after {MAX_RETRIES} attempts. "
            "Check internet connection and DNS settings."
        ) from e
    await asyncio.sleep(backoff)

except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as e:
    # Connection or timeout errors
    # ... similar handling with exponential backoff

except asyncio.TimeoutError as e:
    # Async timeout errors
    # ... with clear error messages
```

### 2. Pre-Flight Connectivity Check

**File**: [backend/scanner/tasks/celery_tasks.py](../backend/scanner/tasks/celery_tasks.py)

**Added connectivity check before scanning**:
```python
async with BinanceClient() as client:
    # Pre-flight connectivity check
    logger.info("🔍 Checking Binance API connectivity...")
    is_connected = await client.check_connectivity()

    if not is_connected:
        logger.error(
            "🔴 Cannot connect to Binance API. "
            "Please check:\n"
            "  1. Internet connection is active\n"
            "  2. DNS servers are reachable (try: ping 8.8.8.8)\n"
            "  3. Firewall/VPN not blocking api.binance.com\n"
            "  4. Docker network configuration is correct"
        )
        raise ConnectionError(
            "Failed to connect to Binance API. Check network connectivity."
        )
```

### 3. New Connectivity Check Method

**Added to BinanceClient**:
```python
async def check_connectivity(self) -> bool:
    """
    Check if we can connect to Binance API.
    Returns True if connection successful, False otherwise.
    """
    try:
        async with self.session.get(f"{self.BASE_URL}/api/v3/ping") as response:
            return response.status == 200
    except Exception as e:
        logger.warning(f"Connectivity check failed: {type(e).__name__}: {e}")
        return False
```

### 4. Diagnostic Tool

**Created**: [backend/scripts/test_network_connectivity.py](../backend/scripts/test_network_connectivity.py)

Comprehensive diagnostic script that tests:
- ✅ Docker network configuration
- ✅ Basic internet connectivity (Google DNS)
- ✅ DNS resolution for api.binance.com
- ✅ HTTP connection to Binance
- ✅ Binance API endpoint functionality

---

## 🔧 Troubleshooting Steps

### Step 1: Run Diagnostic Script

```bash
# Inside Docker container
docker exec binancebot_web python backend/scripts/test_network_connectivity.py
```

**Expected Output**:
```
================================================================================
                      NETWORK CONNECTIVITY DIAGNOSTIC
================================================================================

Tests Passed: 5/5

✅ DOCKER        - 2 DNS server(s)
✅ INTERNET      - Reachable
✅ DNS           - Resolved to 1 IP(s)
✅ HTTP          - 45ms latency
✅ API           - 1234 symbols loaded

✅ All tests passed! Binance API is reachable.
```

### Step 2: Check DNS Configuration

```bash
# Check DNS servers in container
docker exec binancebot_web cat /etc/resolv.conf

# Should show nameservers like:
# nameserver 8.8.8.8
# nameserver 8.8.4.4
```

### Step 3: Test Basic Connectivity

```bash
# From Docker host
ping -c 3 8.8.8.8

# From Docker container
docker exec binancebot_web ping -c 3 8.8.8.8
```

### Step 4: Test DNS Resolution

```bash
# From Docker container
docker exec binancebot_web nslookup api.binance.com

# Should return IP addresses like:
# Server:    8.8.8.8
# Address:   8.8.8.8#53
#
# Name:      api.binance.com
# Address:   X.X.X.X
```

---

## 🛠️ Common Solutions

### Solution 1: Add DNS Servers to Docker Compose

**File**: `docker-compose.yml`

```yaml
services:
  backend:
    # ... existing config ...
    dns:
      - 8.8.8.8      # Google DNS
      - 8.8.4.4      # Google DNS Secondary
      - 1.1.1.1      # Cloudflare DNS
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

### Solution 2: Fix Docker Network Mode

If using VPN docker-compose, the network mode might be blocking DNS:

**File**: `docker-compose-with-vpn.yml`

**Problem**:
```yaml
backend:
  network_mode: "service:vpn"  # ❌ Breaks DNS/DB access
```

**Solution**: Use HTTP proxy instead:
```yaml
backend:
  environment:
    - HTTP_PROXY=http://vpn:8080
    - HTTPS_PROXY=http://vpn:8080
  networks:
    - default  # ✅ Can access DB and internet
```

### Solution 3: Restart Docker Network

```bash
# Full Docker network reset
docker-compose down
docker network prune -f
docker-compose up -d
```

### Solution 4: Check Host Internet Connection

```bash
# From host machine
ping -c 3 api.binance.com

# If this fails, check:
# 1. WiFi/Ethernet connection
# 2. Router/modem
# 3. ISP issues
```

### Solution 5: Check Firewall/VPN

```bash
# Temporarily disable firewall (Linux)
sudo ufw disable
docker-compose restart backend celery_worker
sudo ufw enable

# Or add rule
sudo ufw allow out 443/tcp
```

### Solution 6: Use Different DNS

**Edit**: `/etc/docker/daemon.json` (on host)
```json
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
}
```

Then:
```bash
sudo systemctl restart docker
docker-compose up -d
```

---

## 📊 Enhanced Error Messages

The new error handling provides clear guidance:

### DNS Resolution Error:
```
🌐 DNS resolution failed for https://api.binance.com: [Errno -3] Temporary failure in name resolution
   Attempt 1/5. Retrying in 2s...
   This usually means: No internet connection or DNS server unavailable
```

### Connection Error:
```
🔌 Connection error to https://api.binance.com: ClientConnectorError
   Attempt 2/5. Retrying in 4s...
```

### Timeout Error:
```
⏱️  Request timeout to /api/v3/exchangeInfo
   Attempt 3/5. Retrying in 8s...
```

### Pre-Flight Check Failure:
```
🔴 Cannot connect to Binance API.
Please check:
  1. Internet connection is active
  2. DNS servers are reachable (try: ping 8.8.8.8)
  3. Firewall/VPN not blocking api.binance.com
  4. Docker network configuration is correct
```

---

## 🔄 Retry Behavior

### Exponential Backoff Schedule:

| Attempt | Delay | Total Time |
|---------|-------|------------|
| 1       | 0s    | 0s         |
| 2       | 2s    | 2s         |
| 3       | 4s    | 6s         |
| 4       | 8s    | 14s        |
| 5       | 16s   | 30s        |
| Final   | 32s   | 62s        |

**Max backoff**: 60 seconds (prevents excessively long waits)

**Total retry time**: ~62 seconds before giving up

---

## 🎯 Improved Features

### Connection Pooling
```python
connector = aiohttp.TCPConnector(
    limit=100,              # Max 100 total connections
    limit_per_host=30,      # Max 30 per host
    ttl_dns_cache=300,      # Cache DNS for 5 minutes
    force_close=False,      # Reuse connections
    enable_cleanup_closed=True  # Auto cleanup
)
```

**Benefits**:
- ✅ Faster subsequent requests (reuse connections)
- ✅ Reduced DNS lookups (5-minute cache)
- ✅ Better resource management

### Timeout Configuration
```python
timeout = aiohttp.ClientTimeout(
    total=30,      # Max 30s total per request
    connect=10,    # Max 10s to establish connection
    sock_read=10   # Max 10s to read response
)
```

**Benefits**:
- ✅ Prevents hanging requests
- ✅ Fast failure detection
- ✅ Better resource utilization

---

## 🧪 Testing

### Manual Test (from host)
```bash
# Test DNS
nslookup api.binance.com

# Test connectivity
curl -i https://api.binance.com/api/v3/ping

# Test from container
docker exec binancebot_web curl -i https://api.binance.com/api/v3/ping
```

### Automated Test
```bash
# Run diagnostic script
docker exec binancebot_web python backend/scripts/test_network_connectivity.py

# Run Celery task
docker exec binancebot_celery celery -A config call scanner.tasks.celery_tasks.scan_market_continuously
```

### Monitor Logs
```bash
# Watch for improved error messages
docker-compose logs -f celery_worker | grep -E "🌐|🔌|⏱️|🔴"
```

---

## 📝 Prevention

### 1. Health Checks in Docker Compose

Add health checks to ensure connectivity:

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; socket.create_connection(('8.8.8.8', 53), timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 2. Startup Checks

The application now performs connectivity checks before starting heavy operations.

### 3. Monitoring

Set up alerts for repeated connection failures:
```bash
# Count connection errors in last hour
docker-compose logs --since 1h celery_worker | grep -c "DNS resolution failed"
```

---

## 🚀 Deployment

To apply these fixes:

```bash
# 1. Restart services
docker-compose down
docker-compose up -d --build

# 2. Verify connectivity
docker exec binancebot_web python backend/scripts/test_network_connectivity.py

# 3. Check logs
docker-compose logs -f celery_worker

# Should see:
# ✅ "Checking Binance API connectivity..."
# ✅ "Market scan completed: Created=X, Updated=Y..."
```

---

## 📚 Related Documentation

- [OPTIMIZATION_FIXES_NOV8.md](OPTIMIZATION_FIXES_NOV8.md) - All optimization fixes
- [DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md) - Deployment guide
- [Docker Networking](https://docs.docker.com/network/) - Official Docker docs

---

## ⚠️ When to Contact Support

If after trying all solutions, you still see:
```
Cannot resolve https://api.binance.com after 5 attempts
```

**Escalate to**:
1. System administrator (network/firewall issues)
2. ISP (internet connectivity issues)
3. Docker support (Docker networking issues)

**Provide**:
- Output of diagnostic script
- Docker logs: `docker-compose logs > logs.txt`
- Network config: `docker exec binancebot_web cat /etc/resolv.conf`
- Host internet test: `ping api.binance.com`

---

## 📊 Expected Improvements

| Metric | Before | After |
|--------|--------|-------|
| **Error Visibility** | Generic error | Specific error with cause |
| **Retry Strategy** | 3 attempts, fixed delay | 5 attempts, exponential backoff |
| **Max Retry Time** | 6 seconds | 62 seconds |
| **Troubleshooting** | Manual diagnosis | Automated diagnostic tool |
| **Error Recovery** | Often failed | Self-healing with retries |
| **User Guidance** | None | Step-by-step instructions |

---

**Last Updated**: November 8, 2025
**Status**: ✅ Fixed and Tested
**Impact**: Critical - Prevents service failures from transient network issues
