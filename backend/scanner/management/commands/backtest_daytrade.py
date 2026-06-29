"""Backtest the day-trade (15m Market Structure Pullback) engine.

Walks historical 15m + 1h candles through DayTradeSignalEngine.evaluate()
without look-ahead, simulates the active fixed-percentage SL/TP exits, and
reports win rate, profit factor, expectancy and max drawdown. Read-only:
no DB writes, no signals persisted.

Usage:
    python manage.py backtest_daytrade
    python manage.py backtest_daytrade --symbols BTCUSDT,ETHUSDT --days 120
    python manage.py backtest_daytrade --days 90 --output /tmp/dt_baseline.json
"""
import asyncio
import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.indicators.indicator_utils import klines_to_dataframe
from scanner.strategies.daytrade_signal_engine import (
    DayTradeSignalEngine,
    DayTradeSignalConfig,
)

WINDOW_15M = 400
WINDOW_1H = 400
BINANCE_MAX_LIMIT = 1500
WARMUP_15M_DAYS = 6
WARMUP_1H_DAYS = 22


def _interval_ms(interval):
    """Milliseconds per kline interval (supports m/h/d)."""
    factor = {'m': 60_000, 'h': 3_600_000, 'd': 86_400_000}[interval[-1]]
    return int(interval[:-1]) * factor


def _load_config():
    """Build the engine config from the active DayTradeStrategyConfig, or defaults."""
    try:
        from signals.models.daytrade import DayTradeStrategyConfig
        return DayTradeSignalConfig.from_db(DayTradeStrategyConfig.get_active())
    except Exception:
        return DayTradeSignalConfig()


async def _fetch_history(client, symbol, interval, start_ms, end_ms):
    """Page through Binance klines from start_ms to end_ms, de-duplicated by open time."""
    interval_ms = _interval_ms(interval)
    by_open = {}
    cursor = start_ms
    while cursor < end_ms:
        batch = await client.get_klines(
            symbol, interval=interval, limit=BINANCE_MAX_LIMIT,
            start_time=cursor, end_time=end_ms,
        )
        if not batch:
            break
        for row in batch:
            by_open[row[0]] = row
        last_open = batch[-1][0]
        cursor = last_open + interval_ms
        if len(batch) < BINANCE_MAX_LIMIT:
            break
    return [by_open[k] for k in sorted(by_open)]


async def _fetch_symbol_frames(symbol, start_ms, end_ms, entry_tf, trend_tf):
    """Fetch and frame the 15m + 1h history for one symbol."""
    async with BinanceFuturesClient() as client:
        klines_15m = await _fetch_history(
            client, symbol, entry_tf,
            start_ms - WARMUP_15M_DAYS * 86_400_000, end_ms,
        )
        klines_1h = await _fetch_history(
            client, symbol, trend_tf,
            start_ms - WARMUP_1H_DAYS * 86_400_000, end_ms,
        )
    if not klines_15m or not klines_1h:
        return None, None
    return klines_to_dataframe(klines_15m), klines_to_dataframe(klines_1h)


def _simulate_exit(df15, entry_idx, direction, stop_loss, take_profit):
    """Walk forward from entry to the first SL/TP touch.

    SL is checked before TP within the same candle (conservative). Returns
    (exit_idx, exit_price, outcome) with outcome in {'TP', 'SL', 'OPEN'}.
    """
    for j in range(entry_idx + 1, len(df15)):
        high = df15['high'].iloc[j]
        low = df15['low'].iloc[j]
        if direction == 'LONG':
            if low <= stop_loss:
                return j, stop_loss, 'SL'
            if high >= take_profit:
                return j, take_profit, 'TP'
        else:
            if high >= stop_loss:
                return j, stop_loss, 'SL'
            if low <= take_profit:
                return j, take_profit, 'TP'
    return None, None, 'OPEN'


def _trade_pnl(cfg, entry, exit_price, direction):
    """Return (price_move_pct, pnl_usdt) for a closed trade."""
    move = (exit_price - entry) / entry if direction == 'LONG' else (entry - exit_price) / entry
    pnl_usdt = cfg.margin_per_trade * cfg.leverage * move
    return move * 100, pnl_usdt


def _first_eval_index(df15, start_ts):
    """Index of the first 15m candle at or after the evaluation start."""
    for i in range(len(df15)):
        if df15.index[i] >= start_ts:
            return i
    return len(df15)


def _backtest_symbol(engine, cfg, symbol, df15, df1h, start_ts):
    """Walk-forward backtest for one symbol; returns a list of trade dicts."""
    trades = []
    i = _first_eval_index(df15, start_ts)
    n = len(df15)
    while i < n:
        candle_time = df15.index[i]
        df1h_slice = df1h[df1h.index <= candle_time - timedelta(hours=1)].tail(WINDOW_1H)
        df15_slice = df15.iloc[max(0, i - WINDOW_15M + 1):i + 1]

        result = engine.evaluate(symbol, df15_slice, df1h_slice)
        if result is None:
            i += 1
            continue

        exit_idx, exit_price, outcome = _simulate_exit(
            df15, i, result['direction'], result['stop_loss'], result['tp1']
        )
        trades.append(_build_trade(cfg, symbol, df15, i, exit_idx, exit_price, outcome, result))

        if exit_idx is None:
            break
        i = exit_idx + 1
    return trades


def _build_trade(cfg, symbol, df15, entry_idx, exit_idx, exit_price, outcome, result):
    """Assemble a trade record from an entry/exit pair."""
    entry = result['entry']
    trade = {
        'symbol': symbol,
        'direction': result['direction'],
        'entry_time': df15.index[entry_idx].isoformat(),
        'entry_price': round(entry, 8),
        'stop_loss': round(result['stop_loss'], 8),
        'take_profit': round(result['tp1'], 8),
        'confidence': result['confidence'],
        'score': result['score'],
        'outcome': outcome,
    }
    if outcome == 'OPEN':
        trade.update({'exit_time': None, 'exit_price': None, 'pnl_pct': None, 'pnl_usdt': None})
        return trade
    pnl_pct, pnl_usdt = _trade_pnl(cfg, entry, exit_price, result['direction'])
    trade.update({
        'exit_time': df15.index[exit_idx].isoformat(),
        'exit_price': round(exit_price, 8),
        'pnl_pct': round(pnl_pct, 4),
        'pnl_usdt': round(pnl_usdt, 4),
    })
    return trade


def _max_drawdown(closed_sorted):
    """Peak-to-trough drawdown of the cumulative USDT equity curve."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for trade in closed_sorted:
        equity += trade['pnl_usdt']
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return round(max_dd, 2)


def _max_consecutive_losses(closed_sorted):
    """Longest run of consecutive losing trades."""
    run = 0
    worst = 0
    for trade in closed_sorted:
        if trade['pnl_usdt'] < 0:
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    return worst


def _summarize(cfg, trades):
    """Compute aggregate metrics over a list of trade dicts."""
    closed = [t for t in trades if t['outcome'] in ('TP', 'SL')]
    open_count = sum(1 for t in trades if t['outcome'] == 'OPEN')
    wins = [t for t in closed if t['pnl_usdt'] > 0]
    losses = [t for t in closed if t['pnl_usdt'] < 0]
    gross_profit = sum(t['pnl_usdt'] for t in wins)
    gross_loss = abs(sum(t['pnl_usdt'] for t in losses))
    closed_sorted = sorted(closed, key=lambda t: t['entry_time'])
    resolved = len(closed)
    sl = cfg.sl_percentage
    tp = cfg.tp_percentage
    return {
        'total_signals': len(trades),
        'resolved_trades': resolved,
        'open_at_end': open_count,
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(len(wins) / resolved * 100, 2) if resolved else 0.0,
        'breakeven_win_rate': round(sl / (sl + tp) * 100, 2) if (sl + tp) else 0.0,
        'net_pnl_usdt': round(gross_profit - gross_loss, 2),
        'gross_profit_usdt': round(gross_profit, 2),
        'gross_loss_usdt': round(gross_loss, 2),
        'profit_factor': round(gross_profit / gross_loss, 3) if gross_loss else None,
        'expectancy_usdt': round((gross_profit - gross_loss) / resolved, 4) if resolved else 0.0,
        'avg_win_usdt': round(gross_profit / len(wins), 2) if wins else 0.0,
        'avg_loss_usdt': round(gross_loss / len(losses), 2) if losses else 0.0,
        'max_drawdown_usdt': _max_drawdown(closed_sorted),
        'max_consecutive_losses': _max_consecutive_losses(closed_sorted),
    }


class Command(BaseCommand):
    help = 'Backtest the day-trade 15m engine over historical Binance futures data'

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default=None, help='Comma list (default: active config symbols)')
        parser.add_argument('--days', type=int, default=90, help='Lookback window in days (default: 90)')
        parser.add_argument('--output', default=None, help='Write full results JSON to this path')

    def handle(self, *args, **options):
        cfg = _load_config()
        symbols = self._resolve_symbols(options['symbols'], cfg)
        end_ms = int(timezone.now().timestamp() * 1000)
        start_ms = end_ms - options['days'] * 86_400_000
        start_ts = timezone.datetime.utcfromtimestamp(start_ms / 1000)

        engine = DayTradeSignalEngine(cfg)
        self.stdout.write(
            f"Backtesting {len(symbols)} symbol(s) over {options['days']}d | "
            f"SL {cfg.sl_percentage}% / TP {cfg.tp_percentage}% | "
            f"min_score {cfg.min_score}/{cfg.max_score} conf {cfg.min_confidence}"
        )

        all_trades = []
        per_symbol = {}
        for symbol in symbols:
            trades = self._run_symbol(engine, cfg, symbol, start_ms, end_ms, start_ts)
            if trades is None:
                continue
            per_symbol[symbol] = _summarize(cfg, trades)
            all_trades.extend(trades)

        overall = _summarize(cfg, all_trades)
        self._print_report(overall, per_symbol)
        self._maybe_write(options['output'], cfg, overall, per_symbol, all_trades, options['days'])

    def _resolve_symbols(self, arg, cfg):
        """Resolve the symbol list from the flag or the active config."""
        if arg:
            return [s.strip().upper() for s in arg.split(',') if s.strip()]
        return cfg.symbols or ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']

    def _run_symbol(self, engine, cfg, symbol, start_ms, end_ms, start_ts):
        """Fetch data and backtest a single symbol, reporting progress."""
        self.stdout.write(f"  {symbol}: fetching candles...")
        df15, df1h = asyncio.run(
            _fetch_symbol_frames(symbol, start_ms, end_ms, cfg.entry_timeframe, cfg.trend_timeframe)
        )
        if df15 is None:
            self.stdout.write(self.style.WARNING(f"  {symbol}: no data, skipping"))
            return None
        trades = _backtest_symbol(engine, cfg, symbol, df15, df1h, start_ts)
        s = _summarize(cfg, trades)
        self.stdout.write(
            f"  {symbol}: {s['resolved_trades']} trades | win {s['win_rate']}% | "
            f"PF {s['profit_factor']} | net ${s['net_pnl_usdt']}"
        )
        return trades

    def _print_report(self, overall, per_symbol):
        """Print the overall metrics block."""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("==== Day-Trade Backtest (baseline) ===="))
        for key, value in overall.items():
            self.stdout.write(f"  {key}: {value}")

    def _maybe_write(self, path, cfg, overall, per_symbol, all_trades, days):
        """Write the full results JSON if an output path was given."""
        if not path:
            return
        payload = {
            'generated_at': timezone.now().isoformat(),
            'days': days,
            'config': {
                'sl_percentage': cfg.sl_percentage, 'tp_percentage': cfg.tp_percentage,
                'min_score': cfg.min_score, 'max_score': cfg.max_score,
                'min_confidence': cfg.min_confidence, 'leverage': cfg.leverage,
                'margin_per_trade': cfg.margin_per_trade,
            },
            'overall': overall,
            'per_symbol': per_symbol,
            'trades': all_trades,
        }
        with open(path, 'w') as handle:
            json.dump(payload, handle, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Wrote results to {path}"))
