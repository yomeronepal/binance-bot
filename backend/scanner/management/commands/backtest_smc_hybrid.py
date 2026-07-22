"""Backtest the hybrid SMC strategy (scored, multi-timeframe, net-of-cost).

Objective Smart-Money-Concept rules + quantitative filters + a confidence score:

  Bias (4h)      : EMA50 vs EMA200 -> only trade with the higher-tf bias.
  Structure (1h) : prevailing BOS/CHoCH direction must agree (scored).
  Signal (entry-tf, default 15m): liquidity sweep, strong displacement
    (body > mult x ATR), order block, FVG, premium/discount, volume.
  Entry          : wait for a retracement into the order block, then enter.
  Exit           : ATR stop below the OB; fixed-R target (>= 2R).

Confidence score (max 100): BOS 20, sweep 20, displacement 15, order block 15,
FVG 10, premium/discount 10, volume 10. Trade when score >= --min-score;
>= 80 is flagged 'priority'. Research only: no DB writes, no live orders.
Look-ahead-safe (confirmed swings, as-of higher-tf frames, closed candles).

Usage:
    python manage.py backtest_smc_hybrid --signal-tf 15m --days 365
    python manage.py backtest_smc_hybrid --signal-tf 4h --min-score 65 --days 365
"""
import asyncio
from datetime import timedelta

import numpy as np
from django.core.management.base import BaseCommand
from django.utils import timezone

from scanner.indicators.indicator_utils import calculate_ema, calculate_atr, klines_to_dataframe
from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.management.commands.backtest_daytrade import _fetch_history, _interval_ms
from scanner.management.commands.backtest_ict import (
    _swing_levels, _simulate_exit, _net_pnl, _first_eval_index,
)

WARMUP = 240
WEIGHTS = {'bos': 20, 'sweep': 20, 'displacement': 15, 'order_block': 15,
           'fvg': 10, 'premium_discount': 10, 'volume': 20 - 10}


async def _fetch3(symbol, start_ms, end_ms, sig_tf, struct_tf, bias_tf):
    """Fetch signal + structure + bias frames with warmup."""
    async with BinanceFuturesClient() as client:
        async def hist(tf):
            return await _fetch_history(client, symbol, tf, start_ms - WARMUP * _interval_ms(tf), end_ms)
        ks, kh, kb = await hist(sig_tf), await hist(struct_tf), await hist(bias_tf)
    if not ks or not kh or not kb:
        return None, None, None
    return klines_to_dataframe(ks), klines_to_dataframe(kh), klines_to_dataframe(kb)


def _bias_labels(df):
    """UP/DOWN/'' per bias candle via EMA50 vs EMA200."""
    e50 = calculate_ema(df, 50).values
    e200 = calculate_ema(df, 200).values
    out = []
    for a, b in zip(e50, e200):
        out.append('UP' if (not np.isnan(a) and not np.isnan(b) and a > b)
                   else 'DOWN' if (not np.isnan(a) and not np.isnan(b) and a < b) else '')
    return out


def _struct_dir_series(df, k):
    """Prevailing structure direction (bull/bear/'') per structure candle."""
    highs, lows, closes = df['high'].values, df['low'].values, df['close'].values
    last_sh, last_sl = _swing_levels(highs, lows, k)
    out = []
    d = ''
    for i in range(len(closes)):
        if not np.isnan(last_sh[i]) and closes[i] > last_sh[i]:
            d = 'bull'
        elif not np.isnan(last_sl[i]) and closes[i] < last_sl[i]:
            d = 'bear'
        out.append(d)
    return out


def _asof(times, labels, t, delta):
    idx = int(np.searchsorted(times, np.datetime64(t - delta), side='right')) - 1
    return labels[idx] if idx >= 0 else ''


def _score_long(f, closes, opens, highs, lows, vols, atr, vol_sma, last_sh, last_sl,
                ob_idx, mid, h1_ok, opts):
    """Confidence score + entry_zone/sl for a long setup at candle f (None if no trigger)."""
    a = atr[f]
    body = abs(closes[f] - opens[f])
    if body < opts['disp_mult'] * a:              # displacement is the trigger
        return None
    if ob_idx is None:
        return None
    entry_zone = highs[ob_idx]
    sl = lows[ob_idx] - opts['sl_buffer_atr'] * a
    if entry_zone - sl <= 0:
        return None
    score = WEIGHTS['displacement'] + WEIGHTS['order_block']
    if closes[f] > last_sh[f] and h1_ok:
        score += WEIGHTS['bos']
    swept = any(not np.isnan(last_sl[s]) and lows[s] < last_sl[s] and closes[s] > last_sl[s]
                for s in range(max(1, f - opts['lookback']), f + 1))
    if swept:
        score += WEIGHTS['sweep']
    if lows[f] > highs[f - 2]:
        score += WEIGHTS['fvg']
    if entry_zone <= mid:
        score += WEIGHTS['premium_discount']
    if not np.isnan(vol_sma[f]) and vols[f] > vol_sma[f]:
        score += WEIGHTS['volume']
    return score, entry_zone, sl


def _last_ob(opens, closes, f, look, bullish):
    """Index of the last opposing candle before f (bearish for long / bullish for short)."""
    for b in range(f - 1, max(f - look, 0) - 1, -1):
        if bullish and closes[b] < opens[b]:
            return b
        if not bullish and closes[b] > opens[b]:
            return b
    return None


def _scan(df_sig, ctx, opts):
    """Walk the signal frame, score setups, enter on retracement; return trades."""
    highs, lows, closes = df_sig['high'].values, df_sig['low'].values, df_sig['close'].values
    opens, vols, times = df_sig['open'].values, df_sig['volume'].values, df_sig.index
    atr = calculate_atr(df_sig, 14).values
    vol_sma = df_sig['volume'].rolling(20).mean().values
    last_sh, last_sl = _swing_levels(highs, lows, opts['swing_k'])
    (b_times, b_labels, b_delta), (s_times, s_dir, s_delta) = ctx
    pd_lb, look, rr, rmax = opts['pd_lb'], opts['lookback'], opts['rr'], opts['retrace_max']

    trades = []
    i = max(_first_eval_index(df_sig, opts['start_ts']), pd_lb + 4)
    n = len(df_sig)
    while i < n:
        if np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        t = times[i].to_pydatetime()
        bias = _asof(b_times, b_labels, t, b_delta)
        sdir = _asof(s_times, s_dir, t, s_delta)
        hi = highs[max(0, i - pd_lb):i + 1].max()
        lo = lows[max(0, i - pd_lb):i + 1].min()
        mid = (hi + lo) / 2.0

        setup = None
        if bias == 'UP':
            ob = _last_ob(opens, closes, i, look, bullish=True)
            r = _score_long(i, closes, opens, highs, lows, vols, atr, vol_sma,
                            last_sh, last_sl, ob, mid, sdir == 'bull', opts)
            if r:
                setup = ('LONG', *r)
        elif bias == 'DOWN':
            ob = _last_ob(opens, closes, i, look, bullish=False)
            r = _score_short(i, closes, opens, highs, lows, vols, atr, vol_sma,
                             last_sh, last_sl, ob, mid, sdir == 'bear', opts)
            if r:
                setup = ('SHORT', *r)

        if setup is None or setup[1] < opts['min_score']:
            i += 1
            continue

        direction, score, entry_zone, sl = setup
        fill_idx = None
        for j in range(i + 1, min(i + 1 + rmax, n)):
            if direction == 'LONG' and lows[j] <= entry_zone:
                fill_idx = j
                break
            if direction == 'SHORT' and highs[j] >= entry_zone:
                fill_idx = j
                break
        if fill_idx is None:
            i += 1
            continue

        entry = entry_zone
        risk = entry - sl if direction == 'LONG' else sl - entry
        if risk <= 0:
            i += 1
            continue
        tp = entry + rr * risk if direction == 'LONG' else entry - rr * risk
        exit_idx, exit_price = _simulate_exit(highs, lows, fill_idx, direction, sl, tp)
        if exit_idx is None:
            break
        pnl = _net_pnl(entry, exit_price, direction, opts['notional'], opts['fee'], opts['slip'])
        trades.append({'score': score, 'pnl': pnl, 'direction': direction})
        i = exit_idx + 1
    return trades


def _score_short(f, closes, opens, highs, lows, vols, atr, vol_sma, last_sh, last_sl,
                 ob_idx, mid, h1_ok, opts):
    """Mirror of _score_long for shorts."""
    a = atr[f]
    if abs(closes[f] - opens[f]) < opts['disp_mult'] * a or ob_idx is None:
        return None
    entry_zone = lows[ob_idx]
    sl = highs[ob_idx] + opts['sl_buffer_atr'] * a
    if sl - entry_zone <= 0:
        return None
    score = WEIGHTS['displacement'] + WEIGHTS['order_block']
    if closes[f] < last_sl[f] and h1_ok:
        score += WEIGHTS['bos']
    swept = any(not np.isnan(last_sh[s]) and highs[s] > last_sh[s] and closes[s] < last_sh[s]
                for s in range(max(1, f - opts['lookback']), f + 1))
    if swept:
        score += WEIGHTS['sweep']
    if highs[f] < lows[f - 2]:
        score += WEIGHTS['fvg']
    if entry_zone >= mid:
        score += WEIGHTS['premium_discount']
    if not np.isnan(vol_sma[f]) and vols[f] > vol_sma[f]:
        score += WEIGHTS['volume']
    return score, entry_zone, sl


def _summ(trades):
    n = len(trades)
    if not n:
        return {'trades': 0}
    wins = [t for t in trades if t['pnl'] > 0]
    gp = sum(t['pnl'] for t in wins)
    gl = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    net = gp - gl
    return {'trades': n, 'win_rate': round(len(wins) / n * 100, 1),
            'net_pnl': round(net, 2), 'profit_factor': round(gp / gl, 3) if gl else None,
            'expectancy': round(net / n, 3)}


class Command(BaseCommand):
    help = "Backtest the hybrid SMC strategy (scored, multi-timeframe, net-of-cost)"

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default='BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT')
        parser.add_argument('--days', type=int, default=365)
        parser.add_argument('--signal-tf', default='15m')
        parser.add_argument('--structure-tf', default='1h')
        parser.add_argument('--bias-tf', default='4h')
        parser.add_argument('--min-score', type=int, default=65)
        parser.add_argument('--disp-mult', type=float, default=1.5, help='Displacement: body > mult x ATR')
        parser.add_argument('--swing-k', type=int, default=2)
        parser.add_argument('--lookback', type=int, default=10)
        parser.add_argument('--pd-lookback', type=int, default=20)
        parser.add_argument('--retrace-max', type=int, default=6, help='Bars to wait for OB retracement')
        parser.add_argument('--rr', type=float, default=2.0)
        parser.add_argument('--sl-buffer-atr', type=float, default=0.25)
        parser.add_argument('--fee-rate', type=float, default=0.0004)
        parser.add_argument('--slippage-rate', type=float, default=0.0002)
        parser.add_argument('--margin', type=float, default=100.0)
        parser.add_argument('--leverage', type=float, default=10.0)

    def handle(self, *args, **options):
        end_ms = int(timezone.now().timestamp() * 1000)
        start_ms = end_ms - options['days'] * 86_400_000
        start_ts = timezone.datetime.utcfromtimestamp(start_ms / 1000)
        symbols = [s.strip().upper() for s in options['symbols'].split(',') if s.strip()]
        sig_tf, struct_tf, bias_tf = options['signal_tf'], options['structure_tf'], options['bias_tf']
        opts = {
            'min_score': options['min_score'], 'disp_mult': options['disp_mult'],
            'swing_k': options['swing_k'], 'lookback': options['lookback'],
            'pd_lb': options['pd_lookback'], 'retrace_max': options['retrace_max'],
            'rr': options['rr'], 'sl_buffer_atr': options['sl_buffer_atr'],
            'fee': options['fee_rate'], 'slip': options['slippage_rate'],
            'notional': options['margin'] * options['leverage'], 'start_ts': start_ts,
        }
        b_delta = timedelta(milliseconds=_interval_ms(bias_tf))
        s_delta = timedelta(milliseconds=_interval_ms(struct_tf))
        self.stdout.write(
            f"SMC hybrid | {len(symbols)} symbols | {options['days']}d | "
            f"signal {sig_tf} / struct {struct_tf} / bias {bias_tf} | "
            f"min_score {opts['min_score']} disp {opts['disp_mult']}xATR RR {opts['rr']} | net-of-cost"
        )

        all_trades = []
        for symbol in symbols:
            df_sig, df_struct, df_bias = asyncio.run(_fetch3(symbol, start_ms, end_ms, sig_tf, struct_tf, bias_tf))
            if df_sig is None:
                continue
            ctx = ((df_bias.index.values, _bias_labels(df_bias), b_delta),
                   (df_struct.index.values, _struct_dir_series(df_struct, opts['swing_k']), s_delta))
            all_trades.extend(_scan(df_sig, ctx, opts))

        overall = _summ(all_trades)
        priority = _summ([t for t in all_trades if t['score'] >= 80])
        normal = _summ([t for t in all_trades if 65 <= t['score'] < 80])
        self.stdout.write(f"  OVERALL   trades={overall.get('trades', 0):4d} win={overall.get('win_rate', 0)}% "
                          f"PF={overall.get('profit_factor')} net=${overall.get('net_pnl', 0)} exp={overall.get('expectancy', 0)}")
        self.stdout.write(f"  PRIORITY(>=80) trades={priority.get('trades', 0):4d} win={priority.get('win_rate', 0)}% "
                          f"PF={priority.get('profit_factor')} net=${priority.get('net_pnl', 0)}")
        self.stdout.write(f"  NORMAL(65-79)  trades={normal.get('trades', 0):4d} win={normal.get('win_rate', 0)}% "
                          f"PF={normal.get('profit_factor')} net=${normal.get('net_pnl', 0)}")
