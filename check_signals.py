#!/usr/bin/env python3
"""
Quick script to check recent signals in the database.
Run from project root: python check_signals.py
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from signals.models import Signal
from django.utils import timezone

# Get signals from last hour
one_hour_ago = timezone.now() - timedelta(hours=1)
recent_signals = Signal.objects.filter(
    created_at__gte=one_hour_ago
).order_by('-created_at')

print(f"\n{'='*80}")
print(f"SIGNALS FROM LAST 1 HOUR ({recent_signals.count()} total)")
print(f"{'='*80}\n")

if recent_signals.count() == 0:
    print("❌ No signals found in the last hour!")
    print("\nPossible reasons:")
    print("1. Celery worker is not running")
    print("2. No trading opportunities detected")
    print("3. All signals are being filtered as duplicates")
    print("\nCheck Celery logs for more details.")
else:
    for signal in recent_signals:
        age_minutes = (timezone.now() - signal.created_at).total_seconds() / 60
        print(f"{'='*80}")
        print(f"ID: {signal.id}")
        print(f"Symbol: {signal.symbol.symbol}")
        print(f"Direction: {signal.direction}")
        print(f"Timeframe: {signal.timeframe}")
        print(f"Entry: ${signal.entry}")
        print(f"Stop Loss: ${signal.sl}")
        print(f"Take Profit: ${signal.tp}")
        print(f"Confidence: {signal.confidence:.0%}")
        print(f"Status: {signal.status}")
        print(f"Created: {signal.created_at.strftime('%Y-%m-%d %H:%M:%S')} ({age_minutes:.1f} minutes ago)")
        print(f"Market Type: {signal.market_type}")
        print()

# Check for potential duplicates (same symbol, direction in last hour)
print(f"\n{'='*80}")
print(f"DUPLICATE ANALYSIS")
print(f"{'='*80}\n")

from django.db.models import Count
duplicates = Signal.objects.filter(
    created_at__gte=one_hour_ago,
    status='ACTIVE'
).values('symbol__symbol', 'direction', 'timeframe').annotate(
    count=Count('id')
).filter(count__gt=1)

if duplicates.count() == 0:
    print("✅ No duplicate signals detected (deduplication working correctly)")
else:
    print(f"⚠️  Found {duplicates.count()} symbols with multiple signals:")
    for dup in duplicates:
        print(f"  - {dup['symbol__symbol']} {dup['direction']} {dup['timeframe']}: {dup['count']} signals")

print()
