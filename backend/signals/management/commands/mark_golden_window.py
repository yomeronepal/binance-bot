
from django.core.management.base import BaseCommand
from signals.models import PaperTrade
from datetime import timedelta
import pytz

class Command(BaseCommand):
    help = 'Retroactively marks trades as priority if they fall within Golden Window (NPT)'

    def handle(self, *args, **options):
        # Nepal works on UTC+5:45
        # We process 'created_at' which is timezone aware (UTC in DB)
        
        trades = PaperTrade.objects.all()
        updated_count = 0
        total_checked = 0
        
        # Define windows in minutes from midnight
        # 17:00 - 18:00 -> 1020 - 1080
        # 21:00 - 23:00 -> 1260 - 1380
        
        trades_to_update = []
        
        self.stdout.write("Scanning all paper trades...")
        
        for trade in trades:
            total_checked += 1
            
            # Convert to NPT
            # Assuming trade.created_at is UTC. 
            # If naive, Django usually assumes UTC or server time. 
            # Best to treat as UTC and add offset.
            
            # Use entry_time if available, otherwise created_at
            time_to_check = trade.entry_time if trade.entry_time else trade.created_at
            
            if time_to_check.tzinfo is None:
                # If naive, assume UTC for safety or use formatting
                # However, management commands might get naive datetimes if imports were naive.
                # Ideally imports should be aware.
                pass
            
            # offset = 5h 45m
            npt_time = time_to_check + timedelta(hours=5, minutes=45)
            
            day_minutes = npt_time.hour * 60 + npt_time.minute
            
            is_golden_1 = False
            is_golden_2 = False
            
            # Check windows
            # GW1: 17:00-18:00 (1020-1080) OR 21:00-23:00 (1260-1380)
            if (1020 <= day_minutes < 1080) or (1260 <= day_minutes < 1380):
                is_golden_1 = True
                
            # GW2: 21:00-23:00 (1260-1380) AND (Sun, Wed, Thu)
            # Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
            if (1260 <= day_minutes < 1380) and (npt_time.weekday() in [6, 2, 3]):
                is_golden_2 = True
                
            needs_save = False
            if is_golden_1 and not trade.is_priority:
                trade.is_priority = True
                needs_save = True
                
            if is_golden_2 and not trade.is_golden_2:
                trade.is_golden_2 = True
                needs_save = True
                
            if needs_save:
                trades_to_update.append(trade)
                updated_count += 1
                
        if trades_to_update:
            PaperTrade.objects.bulk_update(trades_to_update, ['is_priority', 'is_golden_2'])
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully updated {updated_count} trades (out of {total_checked})."))
        else:
            self.stdout.write(self.style.SUCCESS(f"No trades needed updating (checked {total_checked})."))
