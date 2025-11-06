#!/usr/bin/env python3
"""
Test the multi-timeframe scanner with new indicators
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scanner.tasks.multi_timeframe_scanner import (
    scan_15m_timeframe,
    scan_1h_timeframe,
    scan_4h_timeframe,
    scan_1d_timeframe
)

print("\n" + "="*80)
print("TESTING MULTI-TIMEFRAME SIGNAL SCANNER (15m, 1h, 4h, 1d)")
print("New indicators: SuperTrend, MFI, Parabolic SAR")
print("="*80)

# Test each timeframe
timeframes = [
    (scan_15m_timeframe, "15-minute", "1/4"),
    (scan_1h_timeframe, "1-hour", "2/4"),
    (scan_4h_timeframe, "4-hour", "3/4"),
    (scan_1d_timeframe, "1-day", "4/4")
]

for scan_func, name, progress in timeframes:
    print(f"\n[{progress}] Testing {name} timeframe scan...")
    print("-" * 80)
    try:
        result = scan_func()
        print(f"✅ {name} scan completed!")
        print(f"   Signals created: {result.get('signals_created', 0)}")
        print(f"   Signals updated: {result.get('signals_updated', 0)}")
        print(f"   Signals invalidated: {result.get('signals_invalidated', 0)}")
    except Exception as e:
        print(f"❌ {name} scan failed: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("TESTING COMPLETE")
print("="*80 + "\n")
