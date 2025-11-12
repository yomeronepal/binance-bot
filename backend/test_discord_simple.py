#!/usr/bin/env python3
"""Simple Discord test from Django shell"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scanner.services.discord_notifier import discord_notifier

print("Testing Discord Integration...")
print(f"Webhook configured: {discord_notifier.is_enabled()}")

if discord_notifier.is_enabled():
    print("\n1. Testing connection...")
    if discord_notifier.test_connection():
        print("✅ Connection successful!")

        print("\n2. Testing LONG signal...")
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
        print("✅ LONG signal sent!")

        print("\n3. Testing SHORT signal (FUTURES)...")
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
        print("✅ SHORT signal sent!")

        print("\n✅ All tests complete! Check your Discord channel.")
    else:
        print("❌ Connection test failed!")
else:
    print("❌ Webhook URL not configured!")
