"""Day-trade trading-session optimizer.

Analyzes closed day-trade paper trades by Nepal-time hour and hour-weekday to
discover favourable trading windows, mirroring the v1 golden-window analyzer but
isolated to the DayTrade* models. Results are written as DayTradeSession rows and
used only for analytics / Bot Performance filtering (they do not gate signals).
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from signals.models.daytrade import DayTradePaperTrade, DayTradeSession

logger = logging.getLogger(__name__)

NEPAL_OFFSET = timedelta(hours=5, minutes=45)


def to_nepal_time(dt):
    """Shift a UTC datetime to Nepal time (UTC+5:45)."""
    return dt + NEPAL_OFFSET


def get_closed_trades():
    """Closed, bot-owned day-trade paper trades with an entry timestamp."""
    return DayTradePaperTrade.objects.filter(
        user__isnull=True,
        status__startswith='CLOSED',
        entry_time__isnull=False,
    )


def _is_win(trade):
    """A trade is a win if its realized profit_loss is positive."""
    return (trade.profit_loss or 0) > 0


def analyze_hourly_performance(trades, min_trades=5):
    """Win rate per NPT hour across all days, for hours with enough samples."""
    hourly = defaultdict(lambda: {'wins': 0, 'total': 0, 'losses': 0})
    for trade in trades:
        hour = to_nepal_time(trade.entry_time).hour
        hourly[hour]['total'] += 1
        if _is_win(trade):
            hourly[hour]['wins'] += 1
        else:
            hourly[hour]['losses'] += 1

    result = {}
    for hour, data in hourly.items():
        if data['total'] >= min_trades:
            data['win_rate'] = round(data['wins'] / data['total'] * 100, 2)
            result[hour] = data
    return result


def analyze_hourly_weekday_performance(trades, min_trades=3):
    """Win rate per (NPT hour, weekday), for buckets with enough samples."""
    buckets = defaultdict(lambda: {'wins': 0, 'total': 0})
    for trade in trades:
        npt = to_nepal_time(trade.entry_time)
        key = (npt.hour, npt.weekday())
        buckets[key]['total'] += 1
        if _is_win(trade):
            buckets[key]['wins'] += 1

    result = {}
    for key, data in buckets.items():
        if data['total'] >= min_trades:
            data['win_rate'] = round(data['wins'] / data['total'] * 100, 2)
            result[key] = data
    return result


def _summarize_block(start, end, hours, hourly_data):
    """Aggregate a contiguous hour block into (start, end, avg_win_rate, trades)."""
    total_wins = sum(hourly_data[h]['wins'] for h in hours)
    total_trades = sum(hourly_data[h]['total'] for h in hours)
    win_rate = round(total_wins / total_trades * 100, 2) if total_trades else 0
    return (start, end, win_rate, total_trades)


def _contiguous(qualifying_hours, hourly_data):
    """Group sorted qualifying hours into contiguous (start, end, wr, trades) blocks."""
    if not qualifying_hours:
        return []
    hours = sorted(qualifying_hours)
    blocks = []
    start = end = hours[0]
    run = [hours[0]]
    for h in hours[1:]:
        if h == end + 1:
            end = h
            run.append(h)
        else:
            blocks.append(_summarize_block(start, end + 1, run, hourly_data))
            start = end = h
            run = [h]
    blocks.append(_summarize_block(start, end + 1, run, hourly_data))
    return blocks


def find_all_day_blocks(hourly_data, min_win_rate=60.0):
    """Contiguous all-days hour windows where win rate >= threshold."""
    qualifying = [h for h, d in hourly_data.items() if d['win_rate'] >= min_win_rate]
    return _contiguous(qualifying, hourly_data)


def find_weekday_blocks(hourly_weekday_data, min_win_rate=60.0):
    """Per-weekday hour windows >= threshold, merged across days that share a window."""
    by_day = defaultdict(dict)
    for (hour, weekday), data in hourly_weekday_data.items():
        if data['win_rate'] >= min_win_rate:
            by_day[weekday][hour] = data

    day_blocks = {}
    for weekday, hours_data in by_day.items():
        day_blocks[weekday] = _contiguous(list(hours_data.keys()), hours_data)

    block_to_days = defaultdict(list)
    for weekday, blocks in day_blocks.items():
        for (start, end, wr, trades) in blocks:
            block_to_days[(start, end)].append({'weekday': weekday, 'win_rate': wr, 'trades': trades})

    merged = []
    for (start, end), infos in block_to_days.items():
        days = sorted({i['weekday'] for i in infos})
        if len(days) == 7:
            continue
        total_trades = sum(i['trades'] for i in infos)
        total_wins = sum(int(i['trades'] * i['win_rate'] / 100) for i in infos)
        avg_wr = round(total_wins / total_trades * 100, 2) if total_trades else 0
        merged.append({
            'start_hour': start, 'end_hour': end, 'active_days': days,
            'win_rate': avg_wr, 'total_trades': total_trades,
        })
    return merged


def _upsert_session(name, data, dry_run):
    """Create or update a DayTradeSession by name; returns 'created'/'updated'."""
    if dry_run:
        exists = DayTradeSession.objects.filter(name=name).exists()
        return 'updated' if exists else 'created'
    _, created = DayTradeSession.objects.update_or_create(name=name, defaults=data)
    return 'created' if created else 'updated'


def update_sessions(all_day_blocks, weekday_blocks, dry_run=False):
    """Persist discovered windows as DayTradeSession rows, deactivating stale ones."""
    now = timezone.now()
    changes = {'created': [], 'updated': [], 'deactivated': []}
    used_names = set()

    for start, end, win_rate, total_trades in all_day_blocks:
        name = f"DT-AI-AllDays-{start:02d}00-{end:02d}00"
        used_names.add(name)
        action = _upsert_session(name, {
            'session_type': 'ALL_DAYS', 'start_hour': start, 'end_hour': end,
            'active_days': [], 'is_active': True, 'auto_generated': True,
            'win_rate': win_rate, 'total_trades_analyzed': total_trades,
            'last_optimized_at': now,
            'description': f'Auto: {win_rate}% win rate over {total_trades} trades',
        }, dry_run)
        changes[action].append(name)

    for block in weekday_blocks:
        days = block['active_days']
        day_str = '_'.join(str(d) for d in days)
        name = f"DT-AI-Days{day_str}-{block['start_hour']:02d}00-{block['end_hour']:02d}00"
        used_names.add(name)
        action = _upsert_session(name, {
            'session_type': 'WEEKDAY', 'start_hour': block['start_hour'],
            'end_hour': block['end_hour'], 'active_days': days, 'is_active': True,
            'auto_generated': True, 'win_rate': block['win_rate'],
            'total_trades_analyzed': block['total_trades'], 'last_optimized_at': now,
            'description': f"Auto: {block['win_rate']}% win rate over {block['total_trades']} trades",
        }, dry_run)
        changes[action].append(name)

    if not dry_run:
        stale = DayTradeSession.objects.filter(
            auto_generated=True, is_active=True
        ).exclude(name__in=used_names)
        for session in stale:
            session.is_active = False
            session.save(update_fields=['is_active', 'updated_at'])
            changes['deactivated'].append(session.name)

    return changes


def run_optimization(min_trades=5, min_win_rate=60.0, min_trades_weekday=3, dry_run=False):
    """Run the full day-trade session optimization pipeline."""
    trades = list(get_closed_trades())
    total = len(trades)
    logger.info("DayTrade session optimizer: analyzing %d closed trades", total)

    if total < min_trades:
        return {
            'status': 'skipped',
            'reason': f'Insufficient trades ({total} < {min_trades})',
            'total_trades': total,
        }

    hourly = analyze_hourly_performance(trades, min_trades)
    hourly_weekday = analyze_hourly_weekday_performance(trades, min_trades_weekday)
    all_day_blocks = find_all_day_blocks(hourly, min_win_rate)
    weekday_blocks = find_weekday_blocks(hourly_weekday, min_win_rate)
    changes = update_sessions(all_day_blocks, weekday_blocks, dry_run)

    logger.info(
        "DayTrade session optimizer: %d all-day, %d weekday windows | "
        "created %d, updated %d, deactivated %d",
        len(all_day_blocks), len(weekday_blocks),
        len(changes['created']), len(changes['updated']), len(changes['deactivated']),
    )
    return {
        'status': 'dry_run' if dry_run else 'completed',
        'total_trades_analyzed': total,
        'min_win_rate': min_win_rate,
        'hourly_analysis': {h: {'win_rate': d['win_rate'], 'wins': d['wins'], 'total': d['total']}
                            for h, d in hourly.items()},
        'all_day_windows': [{'start': s, 'end': e, 'win_rate': wr, 'trades': t}
                            for s, e, wr, t in all_day_blocks],
        'weekday_windows': weekday_blocks,
        'changes': changes,
    }
