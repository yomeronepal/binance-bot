
from django.core.management.base import BaseCommand
from signals.models import PaperTrade
from datetime import timedelta

class Command(BaseCommand):
    help = 'Retroactively marks trades with is_priority and is_golden_2 flags based on entry time'

    def handle(self, *args, **options):
        """
        Updates PaperTrade flags based on entry time:

        is_priority (is_golden_1): True if trade was created during ANY trading window
        - GW1: 16:00-17:00 NPT (960-1020 minutes) - all days
        - GW2: 21:00-23:00 NPT (1260-1380 minutes) - all days

        is_golden_2: True if trade was created during premium windows on specific days
        - GW1: 16:00-17:00 NPT on Sun/Wed/Thu only (weekday 6, 2, 3)
        - GW2: 21:00-23:00 NPT on Sun/Wed/Thu only (weekday 6, 2, 3)
        """
        self.stdout.write("Trading Window Configuration:")
        self.stdout.write("  - GW1: 16:00-17:00 NPT (all days) -> is_priority=True")
        self.stdout.write("  - GW2: 21:00-23:00 NPT (all days) -> is_priority=True")
        self.stdout.write("  - GW1: 16:00-17:00 NPT (Sun/Wed/Thu) -> is_golden_2=True")
        self.stdout.write("  - GW2: 21:00-23:00 NPT (Sun/Wed/Thu) -> is_golden_2=True")

        trades = PaperTrade.objects.all()
        updated_count = 0
        total_checked = 0

        trades_to_update = []

        self.stdout.write(f"\nScanning {trades.count()} paper trades...")

        for trade in trades:
            total_checked += 1

            # Use entry_time if available, otherwise created_at
            time_to_check = trade.entry_time if trade.entry_time else trade.created_at

            # Convert to NPT (UTC + 5h 45m)
            npt_time = time_to_check + timedelta(hours=5, minutes=45)
            day_minutes = npt_time.hour * 60 + npt_time.minute
            weekday = npt_time.weekday()  # 0=Mon, 6=Sun

            # Calculate flags based on time
            is_golden_1 = False
            is_golden_2 = False

            # is_priority (is_golden_1): True if signal is generated during ANY trading window
            # GW1: 16:00-17:00 NPT (960-1020 minutes) - all days
            # GW2: 21:00-23:00 NPT (1260-1380 minutes) - all days
            if (960 <= day_minutes < 1020) or (1260 <= day_minutes < 1380):
                is_golden_1 = True

            # is_golden_2: True if signal is generated during premium windows on specific days
            # GW1: 16:00-17:00 NPT on Sun/Wed/Thu only
            # GW2: 21:00-23:00 NPT on Sun/Wed/Thu only
            if ((960 <= day_minutes < 1020) or (1260 <= day_minutes < 1380)) and (weekday in [6, 2, 3]):
                is_golden_2 = True

            # Check if update is needed
            needs_save = False

            if trade.is_priority != is_golden_1:
                trade.is_priority = is_golden_1
                needs_save = True

            if trade.is_golden_2 != is_golden_2:
                trade.is_golden_2 = is_golden_2
                needs_save = True

            if needs_save:
                trades_to_update.append(trade)
                updated_count += 1

        if trades_to_update:
            PaperTrade.objects.bulk_update(trades_to_update, ['is_priority', 'is_golden_2'])
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully updated {updated_count} trades (out of {total_checked})."))
        else:
            self.stdout.write(self.style.SUCCESS(f"No trades needed updating (checked {total_checked})."))
