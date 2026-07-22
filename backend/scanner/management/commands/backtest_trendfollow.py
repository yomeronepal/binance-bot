"""Backtest a trend-following prototype (breakout-in-trend, ATR R:R).

Research tool only: no DB writes, no engine, no live orders. Enters WITH the
higher-timeframe trend on an entry-timeframe breakout, exits on an ATR stop or
ATR target (or an ATR trailing stop), and reports net-of-cost metrics (fee +
slippage on turnover). Entry/trend timeframes are configurable, so the same
harness tests 15m intraday and 4h/1D swing.

Usage:
    python manage.py backtest_trendfollow --days 90
    python manage.py backtest_trendfollow --entry-tf 4h --trend-tf 1d --days 365 \
        --adx-min 20 --breakout 20 --sl-atr 1.5 --tp-atr 3
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

WARMUP_CANDLES = 220


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


def _trend_array(df_trend, adx_min):
    """Per-trend-candle label: 'UP', 'DOWN', or '' (no confirmed trend)."""
    ema50 = calculate_ema(df_trend, 50)
    ema200 = calculate_ema(df_trend, 200)
    adx, _plus, _minus = calculate_adx(df_trend, 14)
    labels = []
    for e50, e200, a in zip(ema50, ema200, adx):
        if np.isnan(e50) or np.isnan(e200) or np.isnan(a) or a < adx_min:
            labels.append('')
        elif e50 > e200:
            labels.append('UP')
        elif e50 < e200:
            labels.append('DOWN')
        else:
            labels.append('')
    return labels


def _trend_at(h_times, trend_labels, candle_time, trend_delta):
    """Trend from the last trend candle closed at/before candle_time (no look-ahead)."""
    cutoff = np.datetime64(candle_time - trend_delta)
    idx = int(np.searchsorted(h_times, cutoff, side='right')) - 1
    if idx < 0:
        return ''
    return trend_labels[idx]


def _simulate_exit(df, entry_idx, direction, stop_loss, take_profit):
    """Walk forward to the first SL/TP touch (SL checked first, conservative)."""
    highs = df['high'].values
    lows = df['low'].values
    for j in range(entry_idx + 1, len(df)):
        if direction == 'LONG':
            if lows[j] <= stop_loss:
                return j, stop_loss, 'SL'
            if highs[j] >= take_profit:
                return j, take_profit, 'TP'
        else:
            if highs[j] >= stop_loss:
                return j, stop_loss, 'SL'
            if lows[j] <= take_profit:
                return j, take_profit, 'TP'
    return None, None, 'OPEN'


def _simulate_exit_trailing(df, entry_idx, direction, initial_sl, trail_dist):
    """Walk forward with an ATR trailing stop (no fixed target; let winners run)."""
    highs = df['high'].values
    lows = df['low'].values
    stop = initial_sl
    best = None
    for j in range(entry_idx + 1, len(df)):
        if direction == 'LONG':
            if lows[j] <= stop:
                return j, stop, 'TRAIL'
            best = highs[j] if best is None else max(best, highs[j])
            stop = max(stop, best - trail_dist)
        else:
            if highs[j] >= stop:
                return j, stop, 'TRAIL'
            best = lows[j] if best is None else min(best, lows[j])
            stop = min(stop, best + trail_dist)
    return None, None, 'OPEN'


def _net_pnl(entry, exit_price, direction, notional, fee_rate, slippage_rate):
    """Net P/L in USDT after round-trip fee + slippage on turnover."""
    move = (exit_price - entry) / entry if direction == 'LONG' else (entry - exit_price) / entry
    gross = notional * move
    turnover = notional * (1 + exit_price / entry)
    cost = turnover * (fee_rate + slippage_rate)
    return gross - cost


def _backtest_symbol(df_entry, df_trend, start_ts, opts, trend_delta):
    """Walk-forward breakout-in-trend backtest for one symbol; returns trades."""
    atr = calculate_atr(df_entry, 14).values
    highs = df_entry['high'].values
    lows = df_entry['low'].values
    closes = df_entry['close'].values
    times = df_entry.index
    h_times = df_trend.index.values
    trend_labels = _trend_array(df_trend, opts['adx_min'])

    look = opts['breakout']
    notional = opts['margin'] * opts['leverage']
    trades = []
    i = max(_first_eval_index(df_entry, start_ts), look)
    n = len(df_entry)
    while i < n:
        a = atr[i]
        if np.isnan(a) or a <= 0:
            i += 1
            continue
        trend = _trend_at(h_times, trend_labels, times[i].to_pydatetime(), trend_delta)
        prior_high = highs[i - look:i].max()
        prior_low = lows[i - look:i].min()
        entry = closes[i]
        direction = None
        if trend == 'UP' and entry > prior_high:
            direction = 'LONG'
        elif trend == 'DOWN' and entry < prior_low:
            direction = 'SHORT'
        if direction is None:
            i += 1
            continue

        if direction == 'LONG':
            sl = entry - opts['sl_atr'] * a
            tp = entry + opts['tp_atr'] * a
        else:
            sl = entry + opts['sl_atr'] * a
            tp = entry - opts['tp_atr'] * a

        if opts['trail_atr'] > 0:
            exit_idx, exit_price, outcome = _simulate_exit_trailing(df_entry, i, direction, sl, opts['trail_atr'] * a)
        else:
            exit_idx, exit_price, outcome = _simulate_exit(df_entry, i, direction, sl, tp)
        if outcome == 'OPEN':
            break
        pnl = _net_pnl(entry, exit_price, direction, notional, opts['fee_rate'], opts['slippage_rate'])
        trades.append({'direction': direction, 'outcome': outcome, 'pnl': pnl})
        i = exit_idx + 1
    return trades


def _summarize(trades):
    """Aggregate net metrics for a trade list."""
    n = len(trades)
    if not n:
        return {'trades': 0}
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    gp = sum(t['pnl'] for t in wins)
    gl = abs(sum(t['pnl'] for t in losses))
    net = gp - gl
    return {
        'trades': n,
        'win_rate': round(len(wins) / n * 100, 1),
        'net_pnl': round(net, 2),
        'profit_factor': round(gp / gl, 3) if gl else None,
        'expectancy': round(net / n, 3),
        'avg_win': round(gp / len(wins), 2) if wins else 0.0,
        'avg_loss': round(gl / len(losses), 2) if losses else 0.0,
    }


class Command(BaseCommand):
    help = "Backtest a trend-following breakout prototype (net-of-cost, research only)"

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default='BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT')
        parser.add_argument('--days', type=int, default=90)
        parser.add_argument('--entry-tf', default='15m', help='Entry timeframe (e.g. 15m, 4h)')
        parser.add_argument('--trend-tf', default='1h', help='Trend-filter timeframe (e.g. 1h, 1d)')
        parser.add_argument('--adx-min', type=float, default=20.0)
        parser.add_argument('--breakout', type=int, default=20, help='Entry-tf breakout lookback')
        parser.add_argument('--sl-atr', type=float, default=1.5)
        parser.add_argument('--tp-atr', type=float, default=3.0)
        parser.add_argument('--trail-atr', type=float, default=0.0,
                            help='ATR trailing-stop distance; >0 replaces the fixed TP (let winners run)')
        parser.add_argument('--fee-rate', type=float, default=0.0004)
        parser.add_argument('--slippage-rate', type=float, default=0.0002)
        parser.add_argument('--margin', type=float, default=100.0)
        parser.add_argument('--leverage', type=float, default=10.0)

    def handle(self, *args, **options):
        end_ms = int(timezone.now().timestamp() * 1000)
        start_ms = end_ms - options['days'] * 86_400_000
        start_ts = timezone.datetime.utcfromtimestamp(start_ms / 1000)
        symbols = [s.strip().upper() for s in options['symbols'].split(',') if s.strip()]
        entry_tf = options['entry_tf']
        trend_tf = options['trend_tf']
        trend_delta = timedelta(milliseconds=_interval_ms(trend_tf))
        opts = {k: options[k] for k in (
            'adx_min', 'breakout', 'sl_atr', 'tp_atr', 'trail_atr',
            'fee_rate', 'slippage_rate', 'margin', 'leverage')}
        rr = round(options['tp_atr'] / options['sl_atr'], 2)
        exit_desc = f"trail {opts['trail_atr']}xATR" if opts['trail_atr'] > 0 else f"TP {opts['tp_atr']}xATR (R:R {rr})"
        self.stdout.write(
            f"Trend-follow breakout | {len(symbols)} symbols | {options['days']}d | "
            f"entry {entry_tf} trend {trend_tf} | ADX>={opts['adx_min']} breakout={opts['breakout']} "
            f"SL {opts['sl_atr']}xATR {exit_desc} | fee {opts['fee_rate']} slip {opts['slippage_rate']}"
        )

        all_trades = []
        for symbol in symbols:
            df_entry, df_trend = asyncio.run(_fetch_frames(symbol, start_ms, end_ms, entry_tf, trend_tf))
            if df_entry is None or df_trend is None:
                self.stdout.write(self.style.WARNING(f"  {symbol}: no data"))
                continue
            trades = _backtest_symbol(df_entry, df_trend, start_ts, opts, trend_delta)
            s = _summarize(trades)
            self.stdout.write(
                f"  {symbol}: {s.get('trades', 0)} trades | win {s.get('win_rate', 0)}% | "
                f"PF {s.get('profit_factor')} | net ${s.get('net_pnl', 0)}"
            )
            all_trades.extend(trades)

        overall = _summarize(all_trades)
        self.stdout.write("  --- OVERALL ---")
        for k, v in overall.items():
            self.stdout.write(f"  {k}: {v}")
