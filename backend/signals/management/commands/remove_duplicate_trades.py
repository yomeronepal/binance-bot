"""
Remove duplicate paper trades.
Keeps the oldest trade per (symbol, direction, entry_time minute) and deletes the rest.

Usage:
    python manage.py remove_duplicate_trades              # Dry run
    python manage.py remove_duplicate_trades --execute    # Actually delete
    python manage.py remove_duplicate_trades --month 11   # Only November
"""
from collections import defaultdict
from django.core.management.base import BaseCommand
from signals.models import PaperTrade


class Command(BaseCommand):
    help = 'Find and remove duplicate paper trades (keeps oldest per symbol+direction+minute)'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true', help='Actually delete duplicates (default: dry run)')
        parser.add_argument('--month', type=int, help='Only check specific month (1-12)')
        parser.add_argument('--year', type=int, help='Only check specific year')

    def handle(self, *args, **options):
        execute = options['execute']
        month = options.get('month')
        year = options.get('year')

        qs = PaperTrade.objects.filter(entry_time__isnull=False).order_by('id')

        if month:
            qs = qs.filter(entry_time__month=month)
        if year:
            qs = qs.filter(entry_time__year=year)

        self.stdout.write(f"\nScanning {qs.count()} trades...")
        if not execute:
            self.stdout.write(self.style.WARNING("DRY RUN - use --execute to delete\n"))

        groups = defaultdict(list)

        for trade_id, symbol, direction, entry_time in qs.values_list('id', 'symbol', 'direction', 'entry_time'):
            key = f"{symbol}_{direction}_{entry_time.strftime('%Y-%m-%d_%H:%M:%S')}"
            groups[key].append(trade_id)

        duplicates_to_delete = []
        duplicate_groups = 0

        for key, trade_ids in groups.items():
            if len(trade_ids) > 1:
                duplicate_groups += 1
                keep_id = trade_ids[0]
                delete_ids = trade_ids[1:]
                duplicates_to_delete.extend(delete_ids)

                if duplicate_groups <= 10:
                    parts = key.split('_')
                    sym = parts[0]
                    direction = parts[1]
                    time_str = '_'.join(parts[2:])
                    self.stdout.write(
                        f"  {sym} {direction} @ {time_str}: "
                        f"keep #{keep_id}, delete {delete_ids}"
                    )

        if duplicate_groups > 10:
            self.stdout.write(f"  ... and {duplicate_groups - 10} more groups")

        total = qs.count()
        unique = len(groups)
        dupes = len(duplicates_to_delete)

        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f"  Total trades:     {total}")
        self.stdout.write(f"  Unique trades:    {unique}")
        self.stdout.write(f"  Duplicates:       {dupes}")
        self.stdout.write(f"  Duplicate groups: {duplicate_groups}")
        self.stdout.write(f"{'=' * 50}")

        if dupes == 0:
            self.stdout.write(self.style.SUCCESS("\nNo duplicates found."))
            return

        if not execute:
            self.stdout.write(self.style.WARNING(f"\nWould delete {dupes} duplicate trades. Use --execute to proceed."))
            return

        batch_size = 500
        deleted_total = 0
        for i in range(0, len(duplicates_to_delete), batch_size):
            batch = duplicates_to_delete[i:i + batch_size]
            count, _ = PaperTrade.objects.filter(id__in=batch).delete()
            deleted_total += count
            self.stdout.write(f"  Deleted batch {i // batch_size + 1}: {count} trades")

        self.stdout.write(self.style.SUCCESS(f"\nDone. Deleted {deleted_total} duplicate trades."))
