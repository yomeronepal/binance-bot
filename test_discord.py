#!/usr/bin/env python3
"""
Quick Discord Integration Test
Tests Discord notifications without needing Django shell.
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from scanner.services.discord_notifier import discord_notifier

def test_connection():
    """Test Discord webhook connection."""
    print("="*60)
    print("Discord Integration Test".center(60))
    print("="*60)
    print()

    # Check if webhook is configured
    if not discord_notifier.is_enabled():
        print("❌ ERROR: Discord webhook URL not configured!")
        print()
        print("To fix this:")
        print("1. Create a webhook in your Discord channel")
        print("2. Add to backend/.env:")
        print("   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
        print("3. Restart services: docker-compose restart celery")
        print()
        return False

    print(f"✅ Discord webhook configured")
    print()

    # Test connection
    print("Testing connection...")
    if discord_notifier.test_connection():
        print("✅ Connection test successful!")
        print()
        return True
    else:
        print("❌ Connection test failed!")
        print()
        print("Possible issues:")
        print("- Invalid webhook URL")
        print("- Network connectivity problems")
        print("- Webhook deleted in Discord")
        return False


def test_signals():
    """Test signal notifications."""
    print("-"*60)
    print("Testing Signal Notifications")
    print("-"*60)
    print()

    # Test LONG signal (SPOT)
    print("1. Sending LONG signal (SPOT)...")
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

    if discord_notifier.send_signal(long_signal):
        print("   ✅ LONG signal sent successfully")
    else:
        print("   ❌ Failed to send LONG signal")
    print()

    # Test SHORT signal (FUTURES)
    print("2. Sending SHORT signal (FUTURES with 10x leverage)...")
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

    if discord_notifier.send_signal(short_signal):
        print("   ✅ SHORT signal sent successfully")
    else:
        print("   ❌ Failed to send SHORT signal")
    print()


def test_alerts():
    """Test alert notifications."""
    print("-"*60)
    print("Testing Alert Notifications")
    print("-"*60)
    print()

    alerts = [
        ('info', 'Scanner started successfully'),
        ('success', 'Trade executed at optimal price'),
        ('warning', 'High volatility detected - use caution'),
        ('error', 'API rate limit reached')
    ]

    for alert_type, message in alerts:
        print(f"Sending {alert_type.upper()} alert...")
        if discord_notifier.send_alert(alert_type, message):
            print(f"   ✅ {alert_type.upper()} alert sent")
        else:
            print(f"   ❌ Failed to send {alert_type.upper()} alert")
    print()


def test_daily_summary():
    """Test daily summary."""
    print("-"*60)
    print("Testing Daily Summary")
    print("-"*60)
    print()

    stats = {
        'total_signals': 15,
        'long_signals': 9,
        'short_signals': 6,
        'avg_confidence': 0.78,
        'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'BNBUSDT']
    }

    print("Sending daily summary...")
    if discord_notifier.send_daily_summary(stats):
        print("   ✅ Daily summary sent successfully")
    else:
        print("   ❌ Failed to send daily summary")
    print()


def main():
    """Run all tests."""
    # Test connection first
    if not test_connection():
        return

    # Ask user what to test
    print("What would you like to test?")
    print("1. All tests (signals + alerts + summary)")
    print("2. Signals only")
    print("3. Alerts only")
    print("4. Daily summary only")
    print("5. Connection test only (already done)")
    print()

    choice = input("Enter choice (1-5) [1]: ").strip() or "1"

    print()

    if choice == "1":
        test_signals()
        import time
        time.sleep(2)  # Rate limiting
        test_alerts()
        time.sleep(2)
        test_daily_summary()
    elif choice == "2":
        test_signals()
    elif choice == "3":
        test_alerts()
    elif choice == "4":
        test_daily_summary()
    elif choice == "5":
        pass  # Already tested connection
    else:
        print("Invalid choice!")
        return

    print("="*60)
    print("✅ All tests complete!".center(60))
    print("Check your Discord channel for the messages.".center(60))
    print("="*60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
