# Discord Notifications Setup Guide

Complete guide to integrate Discord notifications for trading signals.

---

## Table of Contents
1. [Quick Setup](#quick-setup)
2. [Getting Discord Webhook URL](#getting-discord-webhook-url)
3. [Configuration](#configuration)
4. [Testing](#testing)
5. [Signal Format](#signal-format)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)

---

## Quick Setup

### Step 1: Create Discord Webhook

1. Open Discord and go to your server
2. Right-click on the channel where you want signals → **Edit Channel**
3. Go to **Integrations** → **Webhooks**
4. Click **New Webhook** or **Create Webhook**
5. Name it "Trading Bot" (or any name you prefer)
6. (Optional) Upload a custom avatar
7. Click **Copy Webhook URL**

**Example webhook URL:**
```
https://discord.com/api/webhooks/123456789012345678/AbCdEfGhIjKlMnOpQrStUvWxYz1234567890AbCdEfGhIjKlMnOpQr
```

### Step 2: Add Webhook to Environment

**Option A: Update .env file**
```bash
# Edit backend/.env
nano backend/.env

# Add this line:
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE
```

**Option B: Set environment variable (Linux/Mac)**
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE"
```

**Option C: Set environment variable (Windows)**
```cmd
set DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE
```

### Step 3: Restart Services

```bash
# Using Docker
cd docker
docker-compose restart celery

# Or restart all services
docker-compose restart
```

### Step 4: Test Connection

```bash
# Run test script
python backend/manage.py shell << 'EOF'
from scanner.services.discord_notifier import discord_notifier
result = discord_notifier.test_connection()
print(f"Test {'successful' if result else 'failed'}!")
EOF
```

---

## Getting Discord Webhook URL

### Desktop App

1. Open Discord Desktop App
2. Navigate to your server
3. Click on server name → **Server Settings**
4. **Integrations** → **Webhooks** → **New Webhook**
5. Configure webhook:
   - **Name:** Trading Bot
   - **Channel:** Select your signals channel
6. Click **Copy Webhook URL**
7. Save changes

### Web App

1. Go to https://discord.com
2. Select your server
3. Click gear icon next to channel name
4. **Integrations** → **Webhooks** → **New Webhook**
5. Copy webhook URL

### Mobile App

Webhooks cannot be created on mobile. Use desktop or web app.

---

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DISCORD_WEBHOOK_URL` | Discord webhook URL | Yes | None |

### Settings.py

The webhook URL is automatically loaded from environment variables:

```python
# backend/config/settings.py
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
```

### Multiple Webhooks (Optional)

To send signals to multiple channels, create multiple webhooks and separate with commas:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/URL1,https://discord.com/api/webhooks/URL2
```

Then update `discord_notifier.py` to handle multiple URLs.

---

## Testing

### Method 1: Django Shell

```bash
cd backend
python manage.py shell
```

```python
from scanner.services.discord_notifier import discord_notifier

# Test connection
discord_notifier.test_connection()

# Test signal
test_signal = {
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'entry': 50000.0,
    'sl': 49000.0,
    'tp': 52000.0,
    'confidence': 0.85,
    'timeframe': '4h',
    'market_type': 'SPOT'
}
discord_notifier.send_signal(test_signal)

# Test alert
discord_notifier.send_alert('success', 'Test alert successful!')
```

### Method 2: Python Script

Create `test_discord.py`:

```python
#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
sys.path.insert(0, 'backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scanner.services.discord_notifier import discord_notifier

# Test connection
print("Testing Discord connection...")
if discord_notifier.test_connection():
    print("✅ Connection successful!")

    # Test LONG signal
    print("\nTesting LONG signal...")
    long_signal = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 50000.0,
        'sl': 49000.0,
        'tp': 52000.0,
        'confidence': 0.85,
        'timeframe': '4h',
        'market_type': 'SPOT'
    }
    discord_notifier.send_signal(long_signal)

    # Test SHORT signal with leverage
    print("Testing SHORT signal (Futures)...")
    short_signal = {
        'symbol': 'ETHUSDT',
        'direction': 'SHORT',
        'entry': 3000.0,
        'sl': 3100.0,
        'tp': 2800.0,
        'confidence': 0.75,
        'timeframe': '1h',
        'market_type': 'FUTURES',
        'leverage': 10
    }
    discord_notifier.send_signal(short_signal)

    print("\n✅ All tests complete! Check your Discord channel.")
else:
    print("❌ Connection failed! Check your webhook URL.")
```

Run it:
```bash
python test_discord.py
```

### Method 3: Using Docker

```bash
docker-compose exec celery python manage.py shell -c "
from scanner.services.discord_notifier import discord_notifier
print('Testing...', discord_notifier.test_connection())
"
```

---

## Signal Format

### LONG Signal Example

When a LONG signal is detected, Discord will show:

```
🟢 LONG Signal - BTCUSDT 📊

New LONG opportunity detected on 4h timeframe

📍 Entry Price          🎯 Take Profit         🛑 Stop Loss
$50,000.0000           $52,000.0000          $49,000.0000

📊 Risk/Reward          ✨ Confidence          ⏰ Timeframe
1:2.00                  85.0%                 4h

💰 Potential Profit     ⚠️ Potential Loss
+4.00%                  -2.00%

SPOT Market
```

### SHORT Signal Example (Futures)

```
🔴 SHORT Signal - ETHUSDT ⚡

New SHORT opportunity detected on 1h timeframe

📍 Entry Price          🎯 Take Profit         🛑 Stop Loss
$3,000.0000            $2,800.0000           $3,100.0000

📊 Risk/Reward          ✨ Confidence          ⏰ Timeframe
1:2.00                  75.0%                 1h

💰 Potential Profit     ⚠️ Potential Loss
+6.67% (+66.7% with 10x)  -3.33% (-33.3% with 10x)

FUTURES Market • 10x Leverage
```

### Color Coding

- 🟢 **Green**: LONG signals
- 🔴 **Red**: SHORT signals
- 🔵 **Blue**: Alerts and notifications
- 🟡 **Yellow**: Warnings
- ⚫ **Black**: Errors

---

## Advanced Features

### 1. Daily Summary

Send a daily summary of all signals:

```python
from scanner.services.discord_notifier import discord_notifier

stats = {
    'total_signals': 15,
    'long_signals': 9,
    'short_signals': 6,
    'avg_confidence': 0.78,
    'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'BNBUSDT']
}

discord_notifier.send_daily_summary(stats)
```

### 2. Custom Alerts

```python
# Info alert
discord_notifier.send_alert('info', 'Scanner started successfully')

# Warning alert
discord_notifier.send_alert('warning', 'High volatility detected')

# Error alert
discord_notifier.send_alert('error', 'API rate limit reached')

# Success alert
discord_notifier.send_alert('success', 'Trade executed successfully')
```

### 3. Custom Messages

```python
discord_notifier.send_custom_message(
    message="Market conditions are favorable for LONG positions",
    title="Market Analysis",
    color=0x00FF00  # Green
)
```

### 4. Schedule Daily Summaries

Add to `backend/config/celery.py` or create a Celery task:

```python
from celery import shared_task
from scanner.services.discord_notifier import discord_notifier
from signals.models import Signal
from django.utils import timezone
from datetime import timedelta

@shared_task
def send_daily_summary():
    """Send daily trading summary to Discord."""
    today = timezone.now().date()
    signals = Signal.objects.filter(
        created_at__date=today,
        status='ACTIVE'
    )

    stats = {
        'total_signals': signals.count(),
        'long_signals': signals.filter(direction='LONG').count(),
        'short_signals': signals.filter(direction='SHORT').count(),
        'avg_confidence': signals.aggregate(Avg('confidence'))['confidence__avg'] or 0,
        'symbols': list(signals.values_list('symbol__symbol', flat=True).distinct())
    }

    discord_notifier.send_daily_summary(stats)
```

Schedule it in Celery Beat (add to Django admin or celery.py):

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-summary': {
        'task': 'scanner.tasks.send_daily_summary',
        'schedule': crontab(hour=23, minute=59),  # 11:59 PM daily
    },
}
```

---

## Troubleshooting

### Issue 1: "Webhook URL not configured"

**Problem:** Logs show "Discord webhook URL not configured"

**Solution:**
1. Check `.env` file has `DISCORD_WEBHOOK_URL=...`
2. Restart services: `docker-compose restart`
3. Verify with: `docker-compose exec celery env | grep DISCORD`

### Issue 2: "Failed to send Discord notification"

**Problem:** Error when sending messages

**Possible Causes:**
1. **Invalid webhook URL**
   - Check URL is complete and correct
   - Test URL in browser (should show JSON error, not 404)

2. **Webhook deleted**
   - Recreate webhook in Discord
   - Update `.env` with new URL

3. **Rate limiting**
   - Discord limits: 30 requests per minute per webhook
   - If sending many signals, add rate limiting

4. **Network issues**
   - Check internet connection
   - Verify Docker can reach Discord (test with curl)

**Debug:**
```bash
# Test webhook with curl
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message"}'
```

### Issue 3: Messages not appearing

**Problem:** No error but messages don't show in Discord

**Solution:**
1. Check correct channel is selected in webhook settings
2. Verify webhook hasn't been deleted
3. Check Discord permissions (bot needs "Send Messages")
4. Check channel isn't muted

### Issue 4: "discord_notifier not available"

**Problem:** Import error

**Solution:**
```bash
# Restart Celery to reload code
docker-compose restart celery
```

### Issue 5: Unicode/Emoji Issues

**Problem:** Emojis showing as ??? or boxes

**Solution:** Ensure Python environment supports UTF-8:
```bash
export PYTHONIOENCODING=utf-8
```

### Issue 6: Multiple Duplicate Messages

**Problem:** Same signal sent multiple times

**Cause:** Multiple Celery workers processing same signal

**Solution:** This should not happen if deduplication is working. Check:
```python
# In celery_tasks.py, verify duplicate detection is active
if existing_signal:
    logger.info(f"Skipping duplicate signal...")
    return None
```

---

## Security Best Practices

### 1. Keep Webhook URL Secret

⚠️ **Never commit webhook URL to Git!**

```bash
# Add to .gitignore
echo "backend/.env" >> .gitignore
```

### 2. Use Environment Variables

Always load from environment, never hardcode:

```python
# ✅ Good
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# ❌ Bad
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
```

### 3. Rotate Webhooks Regularly

If webhook URL is compromised:
1. Delete old webhook in Discord
2. Create new webhook
3. Update `.env` file
4. Restart services

### 4. Use Separate Webhooks for Dev/Prod

```bash
# Development
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/DEV_WEBHOOK

# Production
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/PROD_WEBHOOK
```

---

## API Reference

### DiscordNotifier Class

#### Methods

**`send_signal(signal_data: Dict) -> bool`**

Send trading signal to Discord.

**Parameters:**
- `signal_data` (dict): Signal information
  - `symbol` (str): Trading pair (e.g., 'BTCUSDT')
  - `direction` (str): 'LONG' or 'SHORT'
  - `entry` (float): Entry price
  - `sl` (float): Stop loss price
  - `tp` (float): Take profit price
  - `confidence` (float): Signal confidence (0-1)
  - `timeframe` (str): Timeframe (e.g., '4h')
  - `market_type` (str, optional): 'SPOT' or 'FUTURES'
  - `leverage` (int, optional): Leverage for futures

**Returns:** `bool` - True if sent successfully

---

**`send_alert(alert_type: str, message: str) -> bool`**

Send alert notification.

**Parameters:**
- `alert_type` (str): Type of alert ('info', 'warning', 'error', 'success')
- `message` (str): Alert message

**Returns:** `bool` - True if sent successfully

---

**`send_custom_message(message: str, title: str = None, color: int = 0x3498db) -> bool`**

Send custom message.

**Parameters:**
- `message` (str): Message content
- `title` (str, optional): Embed title
- `color` (int): Discord color (hex integer)

**Returns:** `bool` - True if sent successfully

---

**`send_daily_summary(stats: Dict) -> bool`**

Send daily trading summary.

**Parameters:**
- `stats` (dict): Statistics dictionary
  - `total_signals` (int): Total signals today
  - `long_signals` (int): Number of LONG signals
  - `short_signals` (int): Number of SHORT signals
  - `avg_confidence` (float): Average confidence (0-1)
  - `symbols` (list): List of symbols traded

**Returns:** `bool` - True if sent successfully

---

**`test_connection() -> bool`**

Test Discord webhook connection.

**Returns:** `bool` - True if connection successful

---

**`is_enabled() -> bool`**

Check if Discord notifications are enabled.

**Returns:** `bool` - True if webhook URL is configured

---

## Example Integration

### Complete Setup Script

```bash
#!/bin/bash
# setup_discord.sh

echo "Discord Notifications Setup"
echo "=========================="
echo ""

# Get webhook URL
read -p "Enter your Discord webhook URL: " WEBHOOK_URL

# Validate URL
if [[ ! $WEBHOOK_URL =~ ^https://discord.com/api/webhooks/ ]]; then
    echo "❌ Invalid webhook URL!"
    exit 1
fi

# Add to .env
echo "" >> backend/.env
echo "# Discord Notifications" >> backend/.env
echo "DISCORD_WEBHOOK_URL=$WEBHOOK_URL" >> backend/.env

echo "✅ Webhook URL saved to .env"

# Restart services
echo "Restarting services..."
cd docker && docker-compose restart celery

echo ""
echo "✅ Setup complete!"
echo ""
echo "Test with:"
echo "  python test_discord.py"
```

Make it executable and run:
```bash
chmod +x setup_discord.sh
./setup_discord.sh
```

---

## Summary

1. ✅ Create Discord webhook in your channel
2. ✅ Add `DISCORD_WEBHOOK_URL` to `.env`
3. ✅ Restart Celery: `docker-compose restart celery`
4. ✅ Test connection: `discord_notifier.test_connection()`
5. ✅ Signals will now be posted to Discord automatically!

**Notification Types:**
- 📊 New trading signals (LONG/SHORT)
- ⚠️ Alerts (info, warning, error, success)
- 📈 Daily summaries
- 💬 Custom messages

**Features:**
- Beautiful embedded messages
- Color-coded by signal type
- Risk/reward calculations
- Leverage information for futures
- Automatic integration with existing scanner

For support or issues, check the troubleshooting section above.
