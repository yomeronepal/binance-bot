#!/usr/bin/env python3
"""Test commodity API integration"""
import asyncio
from scanner.services.commodity_client import CommodityClient

async def test_commodity():
    print("="*60)
    print("TESTING COMMODITY API (API Ninjas)")
    print("="*60)

    client = CommodityClient()

    # Test Gold
    print("\n1. Testing GOLD...")
    klines = await client.get_klines('GOLD', '1d', 1)
    if klines:
        print(f"✅ SUCCESS! Gold price: ${klines[0][1]}")
    else:
        print("❌ FAILED - No data")

    # Test Silver
    print("\n2. Testing SILVER...")
    klines = await client.get_klines('SILVER', '1d', 1)
    if klines:
        print(f"✅ SUCCESS! Silver price: ${klines[0][1]}")
    else:
        print("❌ FAILED - No data")

    # Test Oil
    print("\n3. Testing WTI (Oil)...")
    klines = await client.get_klines('WTI', '1d', 1)
    if klines:
        print(f"✅ SUCCESS! WTI price: ${klines[0][1]}")
    else:
        print("❌ FAILED - No data")

    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(test_commodity())
