# Forex & Commodities - Quick Start Guide

Get your Forex and Commodities signals running in **5 minutes**!

---

## Step 1: Get Your Free API Key (2 minutes)

1. Visit: **https://www.alphavantage.co/support/#api-key**
2. Enter your email address
3. Receive API key instantly (check your inbox)

---

## Step 2: Configure API Key (1 minute)

Edit `backend/.env`:
```bash
# Find this line:
ALPHAVANTAGE_API_KEY=demo

# Replace with your key:
ALPHAVANTAGE_API_KEY=YOUR_ACTUAL_KEY_HERE
```

---

## Step 3: Restart Services (1 minute)

```bash
docker restart binancebot_web binancebot_celery_beat
```

Wait 30 seconds for services to start.

---

## Step 4: Verify It's Working (1 minute)

### Check Celery Beat is scheduling Forex tasks:
```bash
docker logs binancebot_celery_beat | grep forex
```

**Expected output**:
```
[INFO] DatabaseScheduler: scan-forex-1h-timeframe scheduled
[INFO] DatabaseScheduler: scan-forex-4h-timeframe scheduled
[INFO] DatabaseScheduler: scan-forex-1d-timeframe scheduled
```

### Test Forex integration:
```bash
docker exec binancebot_web python test_forex_integration.py
```

**Expected**: At least "Celery Integration" test passes

---

## Step 5: Monitor Signals

### Via API:
```bash
# All Forex signals
curl http://localhost:8000/api/signals/?market_type=FOREX

# Gold signals
curl http://localhost:8000/api/signals/?symbol=XAUUSD

# 4h timeframe signals
curl http://localhost:8000/api/signals/?timeframe=4h
```

### Via Logs:
```bash
docker logs -f binancebot_web | grep -i "forex\|xau\|xag\|oil"
```

---

## What You're Scanning

### Forex Pairs (7 major pairs)
- EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD

### Commodities (7 symbols)
- **Gold** (XAUUSD)
- **Silver** (XAGUSD)
- **Platinum** (XPTUSD)
- **Palladium** (XPDUSD)
- **WTI Oil** (USOIL)
- **Brent Oil** (UKOIL)
- **Natural Gas** (NATGAS)

---

## Scan Schedule

| When | What | Timeframe |
|------|------|-----------|
| **Every 15 min** | Forex only | 15m (scalping) |
| **Every hour (:10)** | Forex + Commodities | 1h (intraday) |
| **Every 4h (:10)** | Forex + Commodities | 4h (swing) |
| **Daily (00:10)** | Forex + Commodities | 1d (position) |

**Next scans**:
- **15m**: :00, :15, :30, :45
- **1h**: :10 past every hour
- **4h**: 00:10, 04:10, 08:10, 12:10, 16:10, 20:10
- **1d**: 00:10 UTC daily

---

## Trading Parameters

All Forex/Commodity signals use:

- **Stop Loss**: 3.0 × ATR (breathing room)
- **Take Profit**: 9.0 × ATR (1:3 risk/reward)
- **Min Confidence**: 70%
- **ADX**: >= 20 (trend strength)
- **RSI**: 25-35 (LONG) or 65-75 (SHORT)

**Example Trade**:
- Symbol: XAUUSD (Gold)
- Entry: $1850.00
- ATR: $10.00
- Stop Loss: $1850 - (3.0 × $10) = **$1820.00** (risk $30)
- Take Profit: $1850 + (9.0 × $10) = **$1940.00** (reward $90)
- **Risk/Reward**: 1:3

---

## Troubleshooting

### No signals appearing?

**Check 1**: Is Celery Beat running?
```bash
docker ps | grep celery_beat
```

**Check 2**: Is API key valid?
```bash
docker exec binancebot_web python -c "import os; print(os.getenv('ALPHAVANTAGE_API_KEY', 'NOT SET'))"
```

**Check 3**: Test manually:
```bash
docker exec binancebot_web python test_forex_integration.py
```

### Rate limit errors?

You're hitting the 500 requests/day limit.

**Solutions**:
1. Reduce scan frequency (edit `backend/config/celery.py`)
2. Scan fewer pairs (remove minor/exotic)
3. Upgrade to paid Alpha Vantage plan ($50/month)

---

## Need Help?

**Full Documentation**: [FOREX_COMMODITIES_INTEGRATION.md](FOREX_COMMODITIES_INTEGRATION.md)

**Test Script**: Run `docker exec binancebot_web python test_forex_integration.py`

**API Status**: Check https://www.alphavantage.co/

---

**Status**: 🚀 **You're now trading Forex + Commodities!**

Watch for your first signals on the next scan cycle.
