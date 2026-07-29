"""
Golden Window Analyzer Service.
Analyzes paper trade performance by hour and weekday to find optimal trading windows.
Auto-updates TradingSession records when win rate >= threshold.
"""
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional

from django.utils import timezone

from signals.models import PaperTrade, TradingSession

logger = logging.getLogger(__name__)

NEPAL_OFFSET = timedelta(hours=5, minutes=45)


def to_nepal_time(dt):
    """
    Convert UTC datetime to Nepal Time.

    Args:
        dt: UTC datetime

    Returns:
        datetime shifted to NPT
    """
    return dt + NEPAL_OFFSET


def get_closed_trades():
    """
    Get closed paper trades with valid entry times, excluding skipped ones.

    Trades tagged with a skip_reason (ones a live gate such as the circuit
    breaker would have skipped) are excluded, so golden windows are optimized
    from only the trades the bot would actually take.

    Returns:
        QuerySet of closed PaperTrade objects
    """
    return PaperTrade.objects.filter(
        status__startswith='CLOSED',
        entry_time__isnull=False,
        skip_reason='',
    )


def analyze_hourly_performance(min_trades=5):
    """
    Analyze win rate per NPT hour across all days.

    Args:
        min_trades: Minimum trades per hour for statistical significance

    Returns:
        Dict mapping hour (0-23) to {wins, total, win_rate, losses}
    """
    trades = get_closed_trades()
    hourly = defaultdict(lambda: {'wins': 0, 'total': 0, 'losses': 0})

    for trade in trades.only('entry_time', 'profit_loss'):
        npt = to_nepal_time(trade.entry_time)
        hour = npt.hour
        hourly[hour]['total'] += 1
        if trade.profit_loss > 0:
            hourly[hour]['wins'] += 1
        else:
            hourly[hour]['losses'] += 1

    result = {}
    for hour, data in sorted(hourly.items()):
        if data['total'] >= min_trades:
            data['win_rate'] = round(data['wins'] / data['total'] * 100, 2)
            result[hour] = data

    return result


def analyze_hourly_weekday_performance(min_trades=3):
    """
    Analyze win rate per (hour, weekday) combination.

    Args:
        min_trades: Minimum trades per slot for significance

    Returns:
        Dict mapping (hour, weekday) to {wins, total, win_rate}
    """
    trades = get_closed_trades()
    slots = defaultdict(lambda: {'wins': 0, 'total': 0, 'losses': 0})

    for trade in trades.only('entry_time', 'profit_loss'):
        npt = to_nepal_time(trade.entry_time)
        key = (npt.hour, npt.weekday())
        slots[key]['total'] += 1
        if trade.profit_loss > 0:
            slots[key]['wins'] += 1
        else:
            slots[key]['losses'] += 1

    result = {}
    for key, data in sorted(slots.items()):
        if data['total'] >= min_trades:
            data['win_rate'] = round(data['wins'] / data['total'] * 100, 2)
            result[key] = data

    return result


def find_contiguous_blocks(hourly_data, min_win_rate=60.0):
    """
    Find contiguous hour blocks where win rate >= threshold.

    Args:
        hourly_data: Dict from analyze_hourly_performance
        min_win_rate: Minimum win rate % to qualify

    Returns:
        List of (start_hour, end_hour, avg_win_rate, total_trades) tuples
    """
    qualifying = sorted(
        h for h, d in hourly_data.items() if d['win_rate'] >= min_win_rate
    )

    if not qualifying:
        return []

    blocks = []
    block_start = qualifying[0]
    block_end = qualifying[0]
    block_hours = [qualifying[0]]

    for h in qualifying[1:]:
        if h == block_end + 1:
            block_end = h
            block_hours.append(h)
        else:
            blocks.append(_summarize_block(block_start, block_end + 1, block_hours, hourly_data))
            block_start = h
            block_end = h
            block_hours = [h]

    blocks.append(_summarize_block(block_start, block_end + 1, block_hours, hourly_data))
    return blocks


def _summarize_block(start, end, hours, hourly_data):
    """
    Summarize a contiguous block of hours.

    Args:
        start: Start hour
        end: End hour (exclusive)
        hours: List of hours in the block
        hourly_data: Raw hourly data dict

    Returns:
        Tuple of (start_hour, end_hour, avg_win_rate, total_trades)
    """
    total_wins = sum(hourly_data[h]['wins'] for h in hours)
    total_trades = sum(hourly_data[h]['total'] for h in hours)
    avg_wr = round(total_wins / total_trades * 100, 2) if total_trades > 0 else 0
    return (start, end, avg_wr, total_trades)


def find_weekday_blocks(hourly_weekday_data, min_win_rate=60.0):
    """
    Find hour blocks per weekday where win rate >= threshold.
    Used for GW2 (day-specific windows).

    Args:
        hourly_weekday_data: Dict from analyze_hourly_weekday_performance
        min_win_rate: Minimum win rate %

    Returns:
        Dict mapping frozenset(weekdays) to list of (start, end, win_rate, trades)
    """
    by_day = defaultdict(dict)
    for (hour, weekday), data in hourly_weekday_data.items():
        if data['win_rate'] >= min_win_rate:
            by_day[weekday][hour] = data

    day_blocks = {}
    for weekday, hours_data in by_day.items():
        qualifying = sorted(hours_data.keys())
        if not qualifying:
            continue

        blocks = []
        start = qualifying[0]
        end = qualifying[0]
        block_hours = [qualifying[0]]

        for h in qualifying[1:]:
            if h == end + 1:
                end = h
                block_hours.append(h)
            else:
                blocks.append(_summarize_block(start, end + 1, block_hours, hours_data))
                start = h
                end = h
                block_hours = [h]

        blocks.append(_summarize_block(start, end + 1, block_hours, hours_data))
        day_blocks[weekday] = blocks

    merged = _merge_day_blocks(day_blocks)
    return merged


def _merge_day_blocks(day_blocks):
    """
    Merge identical hour blocks across weekdays into GW2 sessions.
    e.g., if Sun, Wed, Thu all have 21:00-23:00, merge into one session with active_days=[6,2,3].

    Args:
        day_blocks: Dict mapping weekday to list of blocks

    Returns:
        List of dicts with start, end, active_days, win_rate, trades
    """
    block_to_days = defaultdict(list)

    for weekday, blocks in day_blocks.items():
        for (start, end, wr, trades) in blocks:
            block_to_days[(start, end)].append({
                'weekday': weekday,
                'win_rate': wr,
                'trades': trades,
            })

    results = []
    for (start, end), day_infos in block_to_days.items():
        days = sorted(set(d['weekday'] for d in day_infos))
        if len(days) == 7:
            continue

        total_trades = sum(d['trades'] for d in day_infos)
        total_wins = sum(
            int(d['trades'] * d['win_rate'] / 100) for d in day_infos
        )
        avg_wr = round(total_wins / total_trades * 100, 2) if total_trades > 0 else 0

        results.append({
            'start_hour': start,
            'end_hour': end,
            'active_days': days,
            'win_rate': avg_wr,
            'total_trades': total_trades,
        })

    return results


def update_trading_sessions(gw1_blocks, gw2_blocks, dry_run=False):
    """
    Update TradingSession records based on analysis results.
    Uses update_or_create to prevent duplicates.
    Deactivates all sessions first, then activates only qualifying ones.

    Args:
        gw1_blocks: List of (start, end, win_rate, trades) for GW1
        gw2_blocks: List of dicts for GW2
        dry_run: If True, don't write to DB

    Returns:
        Dict with created, updated, deactivated counts and details
    """
    now = timezone.now()
    changes = {'created': [], 'updated': [], 'deactivated': []}

    if not dry_run:
        deactivated_count = TradingSession.objects.filter(active=True).update(active=False)
        logger.info(f"Deactivated {deactivated_count} existing sessions")

    used_names = set()

    for start, end, win_rate, total_trades in gw1_blocks:
        name = f"Auto-GW1-{start:02d}00-{end:02d}00"
        used_names.add(name)
        action = _upsert_session(name, {
            'session_type': 'ACTIVE_TRADING_WINDOW',
            'start_hour': start,
            'start_minute': 0,
            'end_hour': end,
            'end_minute': 0,
            'active_days': [],
            'active': True,
            'auto_generated': True,
            'win_rate': Decimal(str(win_rate)),
            'total_trades_analyzed': total_trades,
            'last_optimized_at': now,
            'description': f'Auto-optimized GW1: {win_rate}% win rate from {total_trades} trades',
        }, dry_run)
        changes[action].append(name)

    for block in gw2_blocks:
        start = block['start_hour']
        end = block['end_hour']
        days = block['active_days']
        day_str = '_'.join(str(d) for d in days)
        name = f"Auto-GW2-{start:02d}00-{end:02d}00-D{day_str}"
        used_names.add(name)
        action = _upsert_session(name, {
            'session_type': 'GOLDEN_WINDOW',
            'start_hour': start,
            'start_minute': 0,
            'end_hour': end,
            'end_minute': 0,
            'active_days': days,
            'active': True,
            'auto_generated': True,
            'win_rate': Decimal(str(block['win_rate'])),
            'total_trades_analyzed': block['total_trades'],
            'last_optimized_at': now,
            'description': f'Auto-optimized GW2: {block["win_rate"]}% win rate from {block["total_trades"]} trades',
        }, dry_run)
        changes[action].append(name)

    if not dry_run:
        stale = TradingSession.objects.filter(
            auto_generated=True, active=True
        ).exclude(name__in=used_names)
        for s in stale:
            s.active = False
            s.save(update_fields=['active', 'updated_at'])
            changes['deactivated'].append(s.name)

    return changes


def _upsert_session(name, data, dry_run):
    """
    Create or update a TradingSession by name. Prevents duplicates.

    Args:
        name: Unique session name
        data: Dict of field values
        dry_run: Skip DB write if True

    Returns:
        'created' or 'updated'
    """
    if dry_run:
        exists = TradingSession.objects.filter(name=name).exists()
        return 'updated' if exists else 'created'

    _, created = TradingSession.objects.update_or_create(
        name=name,
        defaults=data
    )
    return 'created' if created else 'updated'


def run_optimization(min_trades=5, min_win_rate=60.0, min_trades_weekday=3, dry_run=False):
    """
    Run the full golden window optimization pipeline.

    Args:
        min_trades: Minimum trades per hour for GW1
        min_win_rate: Minimum win rate % to qualify
        min_trades_weekday: Minimum trades per hour+day for GW2
        dry_run: If True, analyze only, don't update DB

    Returns:
        Dict with analysis results and changes made
    """
    total_closed = get_closed_trades().count()
    logger.info(f"Golden Window Optimizer: analyzing {total_closed} closed trades")

    if total_closed < min_trades:
        logger.warning(f"Only {total_closed} closed trades, need at least {min_trades}. Skipping.")
        return {
            'status': 'skipped',
            'reason': f'Insufficient trades ({total_closed} < {min_trades})',
            'total_trades': total_closed,
        }

    hourly = analyze_hourly_performance(min_trades)
    hourly_weekday = analyze_hourly_weekday_performance(min_trades_weekday)

    gw1_blocks = find_contiguous_blocks(hourly, min_win_rate)
    gw2_blocks = find_weekday_blocks(hourly_weekday, min_win_rate)

    changes = update_trading_sessions(gw1_blocks, gw2_blocks, dry_run)

    result = {
        'status': 'dry_run' if dry_run else 'completed',
        'total_trades_analyzed': total_closed,
        'min_win_rate': min_win_rate,
        'hourly_analysis': {
            h: {
                'win_rate': d['win_rate'],
                'wins': d['wins'],
                'total': d['total'],
            }
            for h, d in hourly.items()
        },
        'gw1_windows': [
            {'start': s, 'end': e, 'win_rate': wr, 'trades': t}
            for s, e, wr, t in gw1_blocks
        ],
        'gw2_windows': gw2_blocks,
        'changes': {
            'created': changes['created'],
            'updated': changes['updated'],
            'deactivated': changes['deactivated'],
        },
    }

    logger.info(
        f"Golden Window Optimization: {len(gw1_blocks)} GW1, {len(gw2_blocks)} GW2 | "
        f"Created: {len(changes['created'])}, Updated: {len(changes['updated'])}, "
        f"Deactivated: {len(changes['deactivated'])}"
    )

    return result
