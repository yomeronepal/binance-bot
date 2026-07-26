"""Net-of-cost backtest + R:R sweep for Signal Engine V1 (RSI mean-reversion).

Reuses the real V1 detection (SignalDetectionEngine._check_long_conditions /
_check_short_conditions) to generate entries on closed candles, then sweeps the
reward:risk ratio on the exits. Entries are independent of SL/TP, so they are
computed once and every R:R re-simulates only the exit. Look-ahead-safe: each
candle is evaluated on a trailing window; exits use only later bars.

Research only; no DB writes, no live orders.

Usage:
    python manage.py backtest_engine_v1 --days 1095 --timeframe 4h
"""
import asyncio

import numpy as np
from django.core.management.base import BaseCommand
from django.utils import timezone

from scanner.indicators.indicator_utils import klines_to_dataframe, calculate_all_indicators
from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.management.commands.backtest_daytrade import _fetch_history
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig

DEFAULT_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT']
WINDOW = 200
RR_SWEEP = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]


async def _load(symbols, interval, start_ms, end_ms):
    out = {}
    async with BinanceFuturesClient() as client:
        for symbol in symbols:
            rows = await _fetch_history(client, symbol, interval, start_ms, end_ms)
            if rows:
                out[symbol] = klines_to_dataframe(rows)
    return out


def _candidate_entries(engine, df, config, symbol):
    """List of (index, direction, entry, atr) V1 signals, ignoring overlap."""
    closes = df['close'].values
    atr = df['atr'].values
    out = []
    for i in range(WINDOW, len(df)):
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(closes[i]):
            continue
        window = df.iloc[i - 1:i + 1]
        current, previous = window.iloc[-1], window.iloc[-2]
        long_sig, long_conf, _l = engine._check_long_conditions(window, current, previous, config, symbol)
        if long_sig and long_conf >= config.min_confidence:
            out.append((i, 'LONG', float(closes[i]), float(atr[i])))
            continue
        short_sig, short_conf, _s = engine._check_short_conditions(window, current, previous, config, symbol)
        if short_sig and short_conf >= config.min_confidence:
            out.append((i, 'SHORT', float(closes[i]), float(atr[i])))
    return out


def _exit(highs, lows, entry_idx, direction, sl, tp):
    """First SL/TP touch after entry (SL first). Returns (exit_price) or None."""
    for j in range(entry_idx + 1, len(highs)):
        if direction == 'LONG':
            if lows[j] <= sl:
                return sl
            if highs[j] >= tp:
                return tp
        else:
            if highs[j] >= sl:
                return sl
            if lows[j] <= tp:
                return tp
    return None


def _net(entry, exit_price, direction, notional, fee, slip):
    move = (exit_price - entry) / entry if direction == 'LONG' else (entry - exit_price) / entry
    turnover = notional * (1 + exit_price / entry)
    return notional * move - turnover * (fee + slip)


def _simulate(candidates, highs, lows, sl_mult, rr, notional, fee, slip):
    """Walk candidate entries with no-overlap; return list of net P/L per trade."""
    pnls = []
    guard = -1
    for idx, direction, entry, atr in candidates:
        if idx <= guard:
            continue
        risk = sl_mult * atr
        if direction == 'LONG':
            sl, tp = entry - risk, entry + rr * risk
        else:
            sl, tp = entry + risk, entry - rr * risk
        exit_price = _exit(highs, lows, idx, direction, sl, tp)
        if exit_price is None:
            break
        pnls.append(_net(entry, exit_price, direction, notional, fee, slip))
        guard = _exit_index(highs, lows, idx, direction, sl, tp)
    return pnls


def _exit_index(highs, lows, entry_idx, direction, sl, tp):
    for j in range(entry_idx + 1, len(highs)):
        if direction == 'LONG' and (lows[j] <= sl or highs[j] >= tp):
            return j
        if direction == 'SHORT' and (highs[j] >= sl or lows[j] <= tp):
            return j
    return len(highs)


def _summ(pnls):
    if not pnls:
        return {'trades': 0, 'win': 0.0, 'pf': 0.0, 'net': 0.0, 'exp': 0.0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    pf = sum(wins) / -sum(losses) if losses and sum(losses) < 0 else 0.0
    return {
        'trades': len(pnls), 'win': 100 * len(wins) / len(pnls), 'pf': pf,
        'net': sum(pnls), 'exp': sum(pnls) / len(pnls),
    }


class Command(BaseCommand):
    help = "Backtest Signal Engine V1 and sweep reward:risk (net-of-cost)"

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default=','.join(DEFAULT_SYMBOLS))
        parser.add_argument('--days', type=int, default=1095)
        parser.add_argument('--timeframe', default='4h')
        parser.add_argument('--min-confidence', type=float, default=None)
        parser.add_argument('--sl-atr', type=float, default=None, help='Fixed SL ATR multiple (default: config)')
        parser.add_argument('--fee-rate', type=float, default=0.0004)
        parser.add_argument('--slippage-rate', type=float, default=0.0002)
        parser.add_argument('--margin', type=float, default=100.0)
        parser.add_argument('--leverage', type=float, default=10.0)

    def handle(self, *args, **options):
        config = SignalConfig()
        config.fib_enable_pullback = False
        if options['min_confidence'] is not None:
            config.min_confidence = options['min_confidence']
        sl_mult = options['sl_atr'] if options['sl_atr'] is not None else config.sl_atr_multiplier
        notional = options['margin'] * options['leverage']
        fee, slip = options['fee_rate'], options['slippage_rate']
        symbols = [s.strip().upper() for s in options['symbols'].split(',') if s.strip()]

        end_ms = int(timezone.now().timestamp() * 1000)
        start_ms = end_ms - options['days'] * 86_400_000
        frames = asyncio.run(_load(symbols, options['timeframe'], start_ms, end_ms))
        engine = SignalDetectionEngine(config, use_volatility_aware=False)

        self.stdout.write(
            f"ENGINE V1 | {len(frames)} symbols | {options['days']}d | {options['timeframe']} | "
            f"conf>={config.min_confidence} | SL {sl_mult}xATR | net fee {fee}+slip {slip} | fib off"
        )
        prepared = self._prepare(frames, engine, config)
        self._sweep(prepared, sl_mult, notional, fee, slip)

    def _prepare(self, frames, engine, config):
        """Compute indicators + candidate entries + bar arrays per symbol (once)."""
        prepared = {}
        total = 0
        for symbol, df in frames.items():
            df = calculate_all_indicators(df)
            cands = _candidate_entries(engine, df, config, symbol)
            prepared[symbol] = (cands, df['high'].values, df['low'].values)
            total += len(cands)
        self.stdout.write(f"  candidate signals detected: {total}")
        return prepared

    def _sweep(self, prepared, sl_mult, notional, fee, slip):
        self.stdout.write("  R:R    trades   win%    PF     net$     exp$")
        best = None
        for rr in RR_SWEEP:
            pnls = []
            for cands, highs, lows in prepared.values():
                pnls.extend(_simulate(cands, highs, lows, sl_mult, rr, notional, fee, slip))
            s = _summ(pnls)
            self.stdout.write(
                f"  1:{rr:<4} {s['trades']:5d}  {s['win']:5.1f}  {s['pf']:5.3f}  "
                f"{s['net']:8.0f}  {s['exp']:6.2f}"
            )
            if s['net'] > (best[1]['net'] if best else -1e18):
                best = (rr, s)
        if best:
            self.stdout.write(
                f"  BEST by net: 1:{best[0]}  (PF {best[1]['pf']:.3f}, net ${best[1]['net']:.0f}, "
                f"{best[1]['trades']} trades)"
            )
