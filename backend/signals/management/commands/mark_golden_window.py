
from django.core.management.base import BaseCommand
from signals.models import PaperTrade, TradingSession
from datetime import timedelta

class Command(BaseCommand):
    help = 'Retroactively marks trades based on TradingSession configurations from database'

    def handle(self, *args, **options):
        # Fetch all active trading sessions from database
        sessions = TradingSession.get_active_sessions()
        
        if not sessions.exists():
            self.stdout.write(self.style.WARNING('⚠️  No active trading sessions found in database.'))
            return
        
        self.stdout.write(f"Found {sessions.count()} active trading session(s):")
        for session in sessions:
            self.stdout.write(f"  - {session.name}: {session}")
        
        trades = PaperTrade.objects.all()
        updated_count = 0
        total_checked = 0
        
        trades_to_update = []
        
        self.stdout.write("\nScanning all paper trades...")
        
        for trade in trades:
            total_checked += 1
            
            # Use entry_time if available, otherwise created_at
            time_to_check = trade.entry_time if trade.entry_time else trade.created_at
            
            # Convert to NPT (UTC + 5h 45m)
            npt_time = time_to_check + timedelta(hours=5, minutes=45)
            
            # Check against all sessions
            needs_save = False
            is_golden_window = False
            is_active_trading_window = False
            
            for session in sessions:
                if session.matches(npt_time):
                    if session.session_type == 'GOLDEN_WINDOW':
                        is_golden_window = True
                    elif session.session_type == 'ACTIVE_TRADING_WINDOW':
                        is_active_trading_window = True
            
            # Update trade flags
            # is_golden_2 = True for GOLDEN_WINDOW matches (premium window)
            # is_priority = True for any trading window match (GOLDEN_WINDOW or ACTIVE_TRADING_WINDOW)
            
            if is_golden_window and not trade.is_golden_2:
                trade.is_golden_2 = True
                needs_save = True
            elif not is_golden_window and trade.is_golden_2:
                trade.is_golden_2 = False
                needs_save = True
                
            if (is_golden_window or is_active_trading_window) and not trade.is_priority:
                trade.is_priority = True
                needs_save = True
            elif not (is_golden_window or is_active_trading_window) and trade.is_priority:
                trade.is_priority = False
                needs_save = True
                
            if needs_save:
                trades_to_update.append(trade)
                updated_count += 1
                
        if trades_to_update:
            PaperTrade.objects.bulk_update(trades_to_update, ['is_priority', 'is_golden_2'])
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully updated {updated_count} trades (out of {total_checked})."))
        else:
            self.stdout.write(self.style.SUCCESS(f"No trades needed updating (checked {total_checked})."))
