"""Portfolio backtest of the 4h order-block ENGINE (exact live behaviour).

Unlike backtest_ict (which trades each symbol independently), this mirrors the
running engine: one shared timeline, skip a new signal while that symbol already
has an open position, cap total concurrent positions, and size fixed-fractional
(risk a % of running equity). Net-of-cost. Research only; no DB writes, no orders.

Usage:
    python manage.py backtest_ob_portfolio --days 1095 --max-concurrent 3 --risk-pct 1.0
"""
import asyncio
from types import SimpleNamespace

import numpy as np
from django.core.management.base import BaseCommand
from django.utils import timezone

from scanner.indicators.indicator_utils import klines_to_dataframe, calculate_atr
from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.management.commands.backtest_daytrade import _fetch_history
from scanner.strategies.order_block_engine import _swing_levels, _order_block_stop

DEFAULT_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT',
    'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'LTCUSDT', 'DOTUSDT', 'ATOMUSDT',
]


async def _load(symbols, start_ms, end_ms):
    out = {}
    async with BinanceFuturesClient() as client:
        for symbol in symbols:
            rows = await _fetch_history(client, symbol, '4h', start_ms, end_ms)
            if rows:
                out[symbol] = klines_to_dataframe(rows)
    return out


def _symbol_signals(df, cfg):
    """Map candle index -> signal dict for every bar where the rule fires."""
    highs, lows = df['high'].values, df['low'].values
    closes, opens = df['close'].values, df['open'].values
    atr = calculate_atr(df, cfg.atr_period).values
    last_sh, last_sl = _swing_levels(highs, lows, cfg.swing_k)
    need = max(cfg.atr_period, cfg.lookback, cfg.swing_k * 2) + 5
    sigs = {}
    for i in range(need, len(df)):
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        for direction in ('LONG', 'SHORT'):
            sl = _order_block_stop(direction, i, opens, closes, highs, lows, last_sh, last_sl, atr[i], cfg)
            if sl is None:
                continue
            entry = closes[i]
            risk = entry - sl if direction == 'LONG' else sl - entry
            if risk <= 0:
                continue
            tp = entry + cfg.rr * risk if direction == 'LONG' else entry - cfg.rr * risk
            sigs[i] = {'direction': direction, 'entry': entry, 'sl': sl, 'tp': tp, 'risk': risk}
            break
    return sigs


def _hit(pos, hi, lo):
    """Return exit price if this bar's range crossed SL/TP (SL first), else None."""
    if pos['direction'] == 'LONG':
        if lo <= pos['sl']:
            return pos['sl']
        if hi >= pos['tp']:
            return pos['tp']
    else:
        if hi >= pos['sl']:
            return pos['sl']
        if lo <= pos['tp']:
            return pos['tp']
    return None


def _net(entry, exit_price, direction, qty, fee, slip):
    move = (exit_price - entry) if direction == 'LONG' else (entry - exit_price)
    turnover = qty * (entry + exit_price)
    return qty * move - turnover * (fee + slip)


class Command(BaseCommand):
    help = "Portfolio backtest of the 4h order-block engine (cap + skip-if-active + fixed-fractional)"

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default=','.join(DEFAULT_SYMBOLS))
        parser.add_argument('--days', type=int, default=1095)
        parser.add_argument('--rr', type=float, default=2.0)
        parser.add_argument('--swing-k', type=int, default=2)
        parser.add_argument('--lookback', type=int, default=10)
        parser.add_argument('--sl-buffer-atr', type=float, default=0.25)
        parser.add_argument('--atr-period', type=int, default=14)
        parser.add_argument('--max-concurrent', type=int, default=5)
        parser.add_argument('--risk-pct', type=float, default=1.0)
        parser.add_argument('--equity', type=float, default=10000.0)
        parser.add_argument('--leverage', type=float, default=10.0)
        parser.add_argument('--fee-rate', type=float, default=0.0004)
        parser.add_argument('--slippage-rate', type=float, default=0.0002)

    def handle(self, *args, **options):
        end_ms = int(timezone.now().timestamp() * 1000)
        start_ms = end_ms - options['days'] * 86_400_000
        symbols = [s.strip().upper() for s in options['symbols'].split(',') if s.strip()]
        cfg = SimpleNamespace(
            atr_period=options['atr_period'], swing_k=options['swing_k'],
            lookback=options['lookback'], sl_buffer_atr=options['sl_buffer_atr'], rr=options['rr'],
        )
        frames = asyncio.run(_load(symbols, start_ms, end_ms))
        self.stdout.write(
            f"OB PORTFOLIO | {len(frames)} symbols | {options['days']}d | cap {options['max_concurrent']} | "
            f"risk {options['risk_pct']}%/trade | RR {cfg.rr} | net fee {options['fee_rate']}+slip {options['slippage_rate']}"
        )
        self._simulate(frames, cfg, options)

    def _prepare(self, frames, cfg):
        """Precompute per-symbol signals + bar arrays + a shared sorted timeline."""
        data = {}
        times = set()
        for symbol, df in frames.items():
            data[symbol] = {
                'sigs': _symbol_signals(df, cfg),
                'highs': df['high'].values, 'lows': df['low'].values,
                'idx': {t: i for i, t in enumerate(df.index)},
            }
            times.update(df.index)
        return data, sorted(times)

    def _simulate(self, frames, cfg, options):
        data, timeline = self._prepare(frames, cfg)
        fee, slip = options['fee_rate'], options['slippage_rate']
        cap, risk_pct, lev = options['max_concurrent'], options['risk_pct'], options['leverage']
        equity = options['equity']
        peak, max_dd = equity, 0.0
        open_pos, trades = {}, []
        sig_total = skip_active = skip_cap = 0

        for t in timeline:
            for symbol in list(open_pos):
                sd = data[symbol]
                j = sd['idx'].get(t)
                if j is None or j <= open_pos[symbol]['entry_i']:
                    continue
                exit_price = _hit(open_pos[symbol], sd['highs'][j], sd['lows'][j])
                if exit_price is None:
                    continue
                pos = open_pos.pop(symbol)
                pnl = _net(pos['entry'], exit_price, pos['direction'], pos['qty'], fee, slip)
                equity += pnl
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak)
                trades.append(pnl)

            for symbol, sd in data.items():
                j = sd['idx'].get(t)
                if j is None or j not in sd['sigs']:
                    continue
                sig_total += 1
                if symbol in open_pos:
                    skip_active += 1
                    continue
                if len(open_pos) >= cap:
                    skip_cap += 1
                    continue
                sig = sd['sigs'][j]
                risk_amt = equity * risk_pct / 100.0
                qty = risk_amt / sig['risk']
                open_pos[symbol] = {**sig, 'qty': qty, 'entry_i': j, 'risk_amt': risk_amt}

        self._report(trades, equity, options['equity'], max_dd, sig_total, skip_active, skip_cap, len(timeline))

    def _report(self, trades, equity, start_equity, max_dd, sig_total, skip_active, skip_cap, bars):
        wins = [p for p in trades if p > 0]
        losses = [p for p in trades if p <= 0]
        pf = sum(wins) / -sum(losses) if losses and sum(losses) < 0 else 0
        n = len(trades)
        net = equity - start_equity
        days = bars * 4 / 24.0
        opened = sig_total - skip_active - skip_cap
        self.stdout.write(
            f"  signals={sig_total} (opened={opened} skip_active={skip_active} skip_cap={skip_cap})  "
            f"~{sig_total / days:.1f} signals/day, {opened / days * 7:.1f} trades/week"
        )
        self.stdout.write(
            f"  trades={n}  win={100 * len(wins) / n:.1f}%  PF={pf:.3f}  "
            f"net=${net:.0f} ({100 * net / start_equity:.1f}%)  maxDD={100 * max_dd:.1f}%  equity=${equity:.0f}"
        )
