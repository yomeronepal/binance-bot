#!/usr/bin/env python
"""
Script to create a PaperAccount for auto-trading testing.
"""
import django
import os
import sys

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from signals.models import PaperAccount
from decimal import Decimal

User = get_user_model()

def main():
    user = User.objects.first()
    if not user:
        print("❌ No users found. Please create a user first.")
        return

    # Create or get PaperAccount
    account, created = PaperAccount.objects.get_or_create(
        user=user,
        defaults={
            'initial_balance': Decimal('1000.00'),
            'balance': Decimal('1000.00'),
            'equity': Decimal('1000.00'),
            'auto_trading_enabled': True,
            'auto_trade_spot': True,
            'auto_trade_futures': True,
            'min_signal_confidence': Decimal('0.70'),
            'max_position_size': Decimal('10.00'),
            'max_open_trades': 5,
        }
    )

    status = "created" if created else "already exists"
    print(f"✅ PaperAccount {status} for user {user.username}")
    print(f"   Balance: ${account.balance}")
    print(f"   Auto-trading: {'ENABLED' if account.auto_trading_enabled else 'DISABLED'}")
    print(f"   Min confidence: {account.min_signal_confidence}")
    print(f"   Max position size: {account.max_position_size}%")
    print(f"   Max open trades: {account.max_open_trades}")

if __name__ == '__main__':
    main()
