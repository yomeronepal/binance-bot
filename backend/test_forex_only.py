#!/usr/bin/env python3
"""Test forex API integration only"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import asyncio
from scanner.services.alphavantage_client import AlphaVantageClient

async def test_forex():
    print("="*60)
    print("TESTING FOREX API (Alpha Vantage)")
    print("="*60)

    client = AlphaVantageClient()

    # Test EURUSD
    print("\n1. Testing EURUSD (1h)...")
    klines = await client.get_klines('EURUSD', '1h', 10)
    if klines:
        print(f"✅ SUCCESS! Got {len(klines)} candles")
        print(f"Latest close: {klines[-1][4]}")
    else:
        print("❌ FAILED - No data")

    # Test GBPUSD
    print("\n2. Testing GBPUSD (1h)...")
    klines = await client.get_klines('GBPUSD', '1h', 10)
    if klines:
        print(f"✅ SUCCESS! Got {len(klines)} candles")
        print(f"Latest close: {klines[-1][4]}")
    else:
        print("❌ FAILED - No data")

    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(test_forex())
