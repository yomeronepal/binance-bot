"""Backtest ICT / Smart-Money-Concept setups (net-of-cost, research only).

Mechanized approximations of three ICT setups so their performance can be
compared apples-to-apples (fixed-R exits, same costs):

  sweep_mss_fvg : liquidity sweep -> market-structure shift -> FVG entry
  fvg_continuation : HTF-trend + fair-value-gap continuation
  order_block : break of structure from the last opposing candle (order block)

No DB writes, no engine, no live orders. Look-ahead-safe: swing points use a
confirmation lag, the trend frame is read as-of the entry candle, and FVG/OB
use only closed candles. ICT is discretionary lore; these are deterministic
proxies, not the "real" thing — treat results as directional evidence.

Usage:
    python manage.py backtest_ict --entry-tf 4h --trend-tf 1d --setup all --days 365
"""
import asyncio
from datetime import timedelta

import numpy as np
from django.core.management.base import BaseCommand
from django.utils import timezone

from scanner.indicators.indicator_utils import (
    calculate_ema, calculate_atr, calculate_adx, klines_to_dataframe,
)
from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.management.commands.backtest_daytrade import _fetch_history, _interval_ms

SETUPS = ['sweep_mss_fvg', 'fvg_continuation', 'order_block']
WARMUP_CANDLES = 240


async def _fetch_frames(symbol, start_ms, end_ms, entry_tf, trend_tf):
    """Fetch entry + trend frames with enough warmup for EMA200/ATR on each tf."""
    e_ms = _interval_ms(entry_tf)
    t_ms = _interval_ms(trend_tf)
    async with BinanceFuturesClient() as client:
        k_entry = await _fetch_history(client, symbol, entry_tf, start_ms - WARMUP_CANDLES * e_ms, end_ms)
        k_trend = await _fetch_history(client, symbol, trend_tf, start_ms - WARMUP_CANDLES * t_ms, end_ms)
    if not k_entry or not k_trend:
        return None, None
    return klines_to_dataframe(k_entry), klines_to_dataframe(k_trend)


def _first_eval_index(df, start_ts):
    """First index at or after start_ts."""
    return int(np.searchsorted(df.index.values, np.datetime64(start_ts), side='left'))


def _swing_levels(highs, lows, k):
    """Most-recent CONFIRMED swing high/low price at each index (k-bar lag)."""
    n = len(highs)
    last_sh = np.full(n, np.nan)
    last_sl = np.full(n, np.nan)
    sh = np.nan
    sl = np.nan
    for j in range(n):
        c = j - k
        if c - k >= 0:
            wh = highs[c - k:c + k + 1]
            wl = lows[c - k:c + k + 1]
            if highs[c] == wh.max():
                sh = highs[c]
            if lows[c] == wl.min():
                sl = lows[c]
        last_sh[j] = sh
        last_sl[j] = sl
    return last_sh, last_sl


def _trend_labels(df_trend, adx_min):
    """UP/DOWN/'' per trend candle (EMA50 vs EMA200 + ADX)."""
    ema50 = calculate_ema(df_trend, 50).values
    ema200 = calculate_ema(df_trend, 200).values
    adx = calculate_adx(df_trend, 14)[0].values
    out = []
    for a50, a200, a in zip(ema50, ema200, adx):
        if np.isnan(a50) or np.isnan(a200) or np.isnan(a) or a < adx_min:
            out.append('')
        elif a50 > a200:
            out.append('UP')
        elif a50 < a200:
            out.append('DOWN')
        else:
            out.append('')
    return out


def _trend_at(h_times, labels, t, delta):
    idx = int(np.searchsorted(h_times, np.datetime64(t - delta), side='right')) - 1
    return labels[idx] if idx >= 0 else ''


def _simulate_exit(highs, lows, entry_idx, direction, sl, tp):
    """First SL/TP touch after entry (SL first). Returns (exit_idx, exit_price) or (None, None)."""
    for j in range(entry_idx + 1, len(highs)):
        if direction == 'LONG':
            if lows[j] <= sl:
                return j, sl
            if highs[j] >= tp:
                return j, tp
        else:
            if highs[j] >= sl:
                return j, sl
            if lows[j] <= tp:
                return j, tp
    return None, None


def _net_pnl(entry, exit_price, direction, notional, fee, slip):
    move = (exit_price - entry) / entry if direction == 'LONG' else (entry - exit_price) / entry
    turnover = notional * (1 + exit_price / entry)
    return notional * move - turnover * (fee + slip)


def _swept_recently(lows, highs, closes, last_sl, last_sh, i, look, direction):
    """True if a liquidity sweep of the opposing level happened in [i-look, i]."""
    for s in range(max(1, i - look), i + 1):
        if direction == 'LONG' and not np.isnan(last_sl[s]):
            if lows[s] < last_sl[s] and closes[s] > last_sl[s]:
                return True
        if direction == 'SHORT' and not np.isnan(last_sh[s]):
            if highs[s] > last_sh[s] and closes[s] < last_sh[s]:
                return True
    return False


def _entries(setup, symbol, df_entry, trend_ctx, opts):
    """Return a list of trade dicts for a setup on one symbol."""
    highs = df_entry['high'].values
    lows = df_entry['low'].values
    closes = df_entry['close'].values
    opens = df_entry['open'].values
    times = df_entry.index
    atr = calculate_atr(df_entry, 14).values
    last_sh, last_sl = _swing_levels(highs, lows, opts['swing_k'])
    h_times, labels, delta = trend_ctx
    look = opts['lookback']
    buf = opts['sl_buffer_atr']
    rr = opts['rr']
    start = max(_first_eval_index(df_entry, opts['start_ts']), look + 4)

    i = start
    n = len(df_entry)
    trades = []
    while i < n:
        a = atr[i]
        if np.isnan(a) or a <= 0:
            i += 1
            continue
        if opts.get('killzone') and times[i].hour not in opts['killzone']:
            i += 1
            continue
        trend = _trend_at(h_times, labels, times[i].to_pydatetime(), delta)
        found = None

        for direction in ('LONG', 'SHORT'):
            entry = closes[i]
            sl = tp = None

            if setup == 'fvg_continuation':
                if direction == 'LONG' and trend == 'UP' and lows[i] > highs[i - 2]:
                    sl = highs[i - 2] - buf * a
                elif direction == 'SHORT' and trend == 'DOWN' and highs[i] < lows[i - 2]:
                    sl = lows[i - 2] + buf * a

            elif setup == 'sweep_mss_fvg':
                swept = _swept_recently(lows, highs, closes, last_sl, last_sh, i, look, direction)
                if direction == 'LONG' and swept and not np.isnan(last_sh[i]) \
                        and closes[i] > last_sh[i] and lows[i] > highs[i - 2]:
                    sl = min(lows[i - look:i + 1]) - buf * a
                elif direction == 'SHORT' and swept and not np.isnan(last_sl[i]) \
                        and closes[i] < last_sl[i] and highs[i] < lows[i - 2]:
                    sl = max(highs[i - look:i + 1]) + buf * a

            elif setup == 'order_block':
                if direction == 'LONG' and not np.isnan(last_sh[i]) and closes[i] > last_sh[i]:
                    obs = [b for b in range(i - 1, max(i - look, 0) - 1, -1) if closes[b] < opens[b]]
                    if obs:
                        sl = lows[obs[0]] - buf * a
                elif direction == 'SHORT' and not np.isnan(last_sl[i]) and closes[i] < last_sl[i]:
                    obs = [b for b in range(i - 1, max(i - look, 0) - 1, -1) if closes[b] > opens[b]]
                    if obs:
                        sl = highs[obs[0]] + buf * a

            if sl is not None and opts.get('require_trend'):
                if (direction == 'LONG' and trend != 'UP') or (direction == 'SHORT' and trend != 'DOWN'):
                    sl = None

            if sl is not None and opts.get('require_pd'):
                lb = opts['pd_lb']
                hi = highs[max(0, i - lb):i + 1].max()
                lo = lows[max(0, i - lb):i + 1].min()
                mid = (hi + lo) / 2.0
                if (direction == 'LONG' and entry > mid) or (direction == 'SHORT' and entry < mid):
                    sl = None

            if sl is not None:
                risk = entry - sl if direction == 'LONG' else sl - entry
                if risk <= 0:
                    continue
                tp = entry + rr * risk if direction == 'LONG' else entry - rr * risk
                found = (direction, entry, sl, tp)
                break

        if found is None:
            i += 1
            continue

        direction, entry, sl, tp = found
        exit_idx, exit_price = _simulate_exit(highs, lows, i, direction, sl, tp)
        if exit_idx is None:
            break
        pnl = _net_pnl(entry, exit_price, direction, opts['notional'], opts['fee'], opts['slip'])
        trades.append({
            'symbol': symbol,
            'setup': setup,
            'direction': direction,
            'entry_time': times[i],
            'entry': round(entry, 8),
            'stop_loss': round(sl, 8),
            'take_profit': round(tp, 8),
            'exit_time': times[exit_idx],
            'exit_price': round(exit_price, 8),
            'outcome': 'SL' if exit_price == sl else 'TP',
            'pnl': round(pnl, 4),
        })
        i = exit_idx + 1
    return trades


def _segment_report(trades, start_ts, end_ts, n):
    """Split (time, pnl) trades into N time buckets and summarize each."""
    if n <= 1 or not trades:
        return []
    span = (end_ts - start_ts) / n
    buckets = [[] for _ in range(n)]
    for t in trades:
        et = t['entry_time'].to_pydatetime().replace(tzinfo=None)
        idx = min(max(int((et - start_ts) / span), 0), n - 1)
        buckets[idx].append(t['pnl'])
    return [((start_ts + span * k).strftime('%Y-%m-%d'), _summarize(buckets[k])) for k in range(n)]


def _summarize(pnls):
    n = len(pnls)
    if not n:
        return {'trades': 0}
    wins = [p for p in pnls if p > 0]
    gp = sum(wins)
    gl = abs(sum(p for p in pnls if p < 0))
    net = gp - gl
    return {
        'trades': n,
        'win_rate': round(len(wins) / n * 100, 1),
        'net_pnl': round(net, 2),
        'profit_factor': round(gp / gl, 3) if gl else None,
        'expectancy': round(net / n, 3),
    }


class Command(BaseCommand):
    help = "Backtest ICT/SMC setups net-of-cost (research only)"

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default='BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT')
        parser.add_argument('--days', type=int, default=365)
        parser.add_argument('--entry-tf', default='4h')
        parser.add_argument('--trend-tf', default='1d')
        parser.add_argument('--setup', default='all', choices=SETUPS + ['all'])
        parser.add_argument('--adx-min', type=float, default=20.0)
        parser.add_argument('--swing-k', type=int, default=2, help='Fractal wing for swing points')
        parser.add_argument('--lookback', type=int, default=10, help='Bars for sweep/OB context')
        parser.add_argument('--rr', type=float, default=2.0)
        parser.add_argument('--sl-buffer-atr', type=float, default=0.25)
        parser.add_argument('--fee-rate', type=float, default=0.0004)
        parser.add_argument('--slippage-rate', type=float, default=0.0002)
        parser.add_argument('--margin', type=float, default=100.0)
        parser.add_argument('--leverage', type=float, default=10.0)
        parser.add_argument('--segments', type=int, default=1,
                            help='Split the window into N walk-forward buckets per setup')
        parser.add_argument('--killzone-hours', default='',
                            help='Comma UTC hours of the entry candle open to allow (ICT killzones), e.g. 8,12')
        parser.add_argument('--require-trend', action='store_true',
                            help='Gate entries by HTF trend alignment (long only UP, short only DOWN)')
        parser.add_argument('--require-pd', action='store_true',
                            help='ICT premium/discount gate: long only in discount, short only in premium')
        parser.add_argument('--pd-lookback', type=int, default=20, help='Dealing-range lookback for premium/discount')
        parser.add_argument('--output', default=None, help='Write the full trade log to this CSV path')
        parser.add_argument('--show-trades', type=int, default=0, help='Print the last N trades per setup')

    def handle(self, *args, **options):
        end_ms = int(timezone.now().timestamp() * 1000)
        start_ms = end_ms - options['days'] * 86_400_000
        start_ts = timezone.datetime.utcfromtimestamp(start_ms / 1000)
        symbols = [s.strip().upper() for s in options['symbols'].split(',') if s.strip()]
        entry_tf, trend_tf = options['entry_tf'], options['trend_tf']
        setups = SETUPS if options['setup'] == 'all' else [options['setup']]
        options['_setups'] = setups
        opts = {
            'adx_min': options['adx_min'], 'swing_k': options['swing_k'],
            'lookback': options['lookback'], 'rr': options['rr'],
            'sl_buffer_atr': options['sl_buffer_atr'],
            'fee': options['fee_rate'], 'slip': options['slippage_rate'],
            'notional': options['margin'] * options['leverage'],
            'start_ts': start_ts,
            'killzone': {int(h) for h in options['killzone_hours'].split(',') if h.strip()},
            'require_trend': options['require_trend'],
            'require_pd': options['require_pd'],
            'pd_lb': options['pd_lookback'],
        }
        delta = timedelta(milliseconds=_interval_ms(trend_tf))
        self.stdout.write(
            f"ICT backtest | {len(symbols)} symbols | {options['days']}d | entry {entry_tf} trend {trend_tf} | "
            f"ADX>={opts['adx_min']} RR {opts['rr']} | net fee {opts['fee']}+slip {opts['slip']}"
        )

        frames = {}
        for symbol in symbols:
            df_entry, df_trend = asyncio.run(_fetch_frames(symbol, start_ms, end_ms, entry_tf, trend_tf))
            if df_entry is not None and df_trend is not None:
                labels = _trend_labels(df_trend, opts['adx_min'])
                frames[symbol] = (df_entry, (df_trend.index.values, labels, delta))

        end_ts = timezone.datetime.utcfromtimestamp(end_ms / 1000)
        for setup in setups:
            all_trades = []
            for symbol, (df_entry, trend_ctx) in frames.items():
                all_trades.extend(_entries(setup, symbol, df_entry, trend_ctx, opts))
            s = _summarize([t['pnl'] for t in all_trades])
            self.stdout.write(
                f"  {setup:18s} trades={s.get('trades', 0):4d} win={s.get('win_rate', 0)}% "
                f"PF={s.get('profit_factor')} net=${s.get('net_pnl', 0)} exp={s.get('expectancy', 0)}"
            )
            if options['segments'] > 1:
                for label, seg in _segment_report(all_trades, start_ts, end_ts, options['segments']):
                    self.stdout.write(
                        f"      {label}: trades={seg.get('trades', 0):4d} "
                        f"PF={seg.get('profit_factor')} net=${seg.get('net_pnl', 0)}"
                    )
            self._emit_trade_log(all_trades, setup, options)

    def _emit_trade_log(self, trades, setup, options):
        """Write trades to CSV (--output) and/or print the last N (--show-trades)."""
        rows = sorted(trades, key=lambda t: t['entry_time'])
        cols = ['symbol', 'setup', 'direction', 'entry_time', 'entry', 'stop_loss',
                'take_profit', 'exit_time', 'exit_price', 'outcome', 'pnl']
        if options.get('output'):
            import csv
            path = options['output']
            if len(options['_setups']) > 1:
                path = path.replace('.csv', f'_{setup}.csv') if path.endswith('.csv') else f"{path}.{setup}"
            with open(path, 'w', newline='') as fh:
                writer = csv.DictWriter(fh, fieldnames=cols)
                writer.writeheader()
                for r in rows:
                    writer.writerow({k: (r[k].isoformat() if hasattr(r[k], 'isoformat') else r[k]) for k in cols})
            self.stdout.write(f"      wrote {len(rows)} trades -> {path}")
        show = options.get('show_trades') or 0
        for r in rows[-show:]:
            self.stdout.write(
                f"      {str(r['entry_time'])[:16]} {r['symbol']:9s} {r['direction']:5s} "
                f"entry {r['entry']} sl {r['stop_loss']} tp {r['take_profit']} "
                f"-> {str(r['exit_time'])[:16]} {r['outcome']} pnl ${r['pnl']}"
            )
