"""
Django management command to create or update PaperAccount
Creates paper trading account for auto-trading testing
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from signals.models import PaperAccount
from decimal import Decimal


User = get_user_model()


class Command(BaseCommand):
    help = 'Create or update PaperAccount for auto-trading testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--balance',
            type=float,
            default=1000.0,
            help='Initial balance for paper account (default: 1000)',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username for the paper account (default: first user)',
        )
        parser.add_argument(
            '--max-trades',
            type=int,
            default=5,
            help='Maximum number of open trades (default: 5)',
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.70,
            help='Minimum signal confidence (default: 0.70)',
        )
        parser.add_argument(
            '--max-position-size',
            type=float,
            default=10.0,
            help='Maximum position size percentage (default: 10.0)',
        )
        parser.add_argument(
            '--disable-auto-trading',
            action='store_true',
            help='Disable auto-trading (default: enabled)',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        # Get user
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ User '{options['user']}' not found"))
                return
        else:
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR("❌ No users found. Please create a user first."))
                return

        # Create or get PaperAccount
        balance = Decimal(str(options['balance']))
        account, created = PaperAccount.objects.get_or_create(
            user=user,
            defaults={
                'initial_balance': balance,
                'balance': balance,
                'equity': balance,
                'auto_trading_enabled': not options['disable_auto_trading'],
                'auto_trade_spot': True,
                'auto_trade_futures': True,
                'min_signal_confidence': Decimal(str(options['min_confidence'])),
                'max_position_size': Decimal(str(options['max_position_size'])),
                'max_open_trades': options['max_trades'],
            }
        )

        # If already exists, update settings
        if not created:
            account.auto_trading_enabled = not options['disable_auto_trading']
            account.min_signal_confidence = Decimal(str(options['min_confidence']))
            account.max_position_size = Decimal(str(options['max_position_size']))
            account.max_open_trades = options['max_trades']
            account.save()

        status = "created" if created else "updated"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"✅ PaperAccount {status} for user {user.username}"))
        self.stdout.write("")
        self.stdout.write("Account Details:")
        self.stdout.write(f"  User:              {user.username}")
        self.stdout.write(f"  Balance:           ${account.balance}")
        self.stdout.write(f"  Auto-trading:      {'ENABLED' if account.auto_trading_enabled else 'DISABLED'}")
        self.stdout.write(f"  Min confidence:    {account.min_signal_confidence}")
        self.stdout.write(f"  Max position size: {account.max_position_size}%")
        self.stdout.write(f"  Max open trades:   {account.max_open_trades}")
        self.stdout.write("")

        if account.auto_trading_enabled:
            self.stdout.write(self.style.SUCCESS("Auto-trading is ENABLED - Signals will be automatically traded"))
        else:
            self.stdout.write(self.style.WARNING("Auto-trading is DISABLED - Use --enable to activate"))
        self.stdout.write("")
