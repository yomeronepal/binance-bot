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
from datetime import datetime, timedelta

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
    """Return (price_move_pct, net_pnl_usdt) for a closed trade.

    Net of round-trip trading costs (fee + slippage on turnover), so the
    backtest reflects the same costs a real fill incurs. Funding is omitted
    (intraday holds make it negligible).
    """
    move = (exit_price - entry) / entry if direction == 'LONG' else (entry - exit_price) / entry
    notional = cfg.margin_per_trade * cfg.leverage
    gross = notional * move
    fee_rate = getattr(cfg, 'bt_fee_rate', 0.0004)
    slippage_rate = getattr(cfg, 'bt_slippage_rate', 0.0002)
    turnover = notional * (1 + exit_price / entry)
    cost = turnover * (fee_rate + slippage_rate)
    return move * 100, gross - cost


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

        target = result['tp2'] if getattr(cfg, 'bt_exit_tp2', False) else result['tp1']
        exit_idx, exit_price, outcome = _simulate_exit(
            df15, i, result['direction'], result['stop_loss'], target
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
        'take_profit': round(result['tp2'] if getattr(cfg, 'bt_exit_tp2', False) else result['tp1'], 8),
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


def _segment_trades(trades, start_ts, end_ts, n):
    """Bucket trades into n equal-time walk-forward segments by entry_time."""
    if n <= 1:
        return [list(trades)]
    span = (end_ts - start_ts).total_seconds()
    buckets = [[] for _ in range(n)]
    if span <= 0:
        buckets[0] = list(trades)
        return buckets
    for trade in trades:
        entered = datetime.fromisoformat(trade['entry_time'])
        frac = (entered - start_ts).total_seconds() / span
        index = min(n - 1, max(0, int(frac * n)))
        buckets[index].append(trade)
    return buckets


class Command(BaseCommand):
    help = 'Backtest the day-trade 15m engine over historical Binance futures data'

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default=None, help='Comma list (default: active config symbols)')
        parser.add_argument('--days', type=int, default=90, help='Lookback window in days (default: 90)')
        parser.add_argument('--output', default=None, help='Write full results JSON to this path')
        parser.add_argument('--structure-v3', action='store_true',
                            help='Enable the V3 graded structure (BOS/CHoCH/significance)')
        parser.add_argument('--min-swing-atr', type=float, default=0.5,
                            help='Significant-swing threshold in ATR units (with --structure-v3)')
        parser.add_argument('--require-bos', action='store_true', help='Require a Break of Structure')
        parser.add_argument('--block-choch', action='store_true', help='Reject on Change of Character')
        parser.add_argument('--structure-bonus', type=float, default=1.0,
                            help='Additive structure-confluence weight (with --structure-v3)')
        parser.add_argument('--trend-filter', action='store_true',
                            help='Enable the V3 trend-strength gate')
        parser.add_argument('--trend-min-slope', type=float, default=0.0,
                            help='Min EMA50 slope %% over the lookback (with --trend-filter)')
        parser.add_argument('--trend-min-gap', type=float, default=0.0,
                            help='Min EMA50-EMA200 gap as %% of price (with --trend-filter)')
        parser.add_argument('--trend-price-above', action='store_true',
                            help='Require price on the trend side of EMA50')
        parser.add_argument('--trend-adx-rising', action='store_true',
                            help='Require 1H ADX to be rising')
        parser.add_argument('--regime-filter', action='store_true',
                            help='Enable the market-regime gate')
        parser.add_argument('--regime-min-adx', type=float, default=0.0,
                            help='Require 15m ADX >= this (with --regime-filter)')
        parser.add_argument('--regime-max-chop', type=float, default=0.0,
                            help='Reject if Choppiness Index > this (e.g. 61.8)')
        parser.add_argument('--regime-min-bbw', type=float, default=0.0,
                            help='Require Bollinger band width %% >= this')
        parser.add_argument('--regime-atr-pct-min', type=float, default=0.0,
                            help='Require ATR percentile (0-100) >= this')
        parser.add_argument('--compare', action='store_true',
                            help='Run baseline (V3 off) vs the V3 config over the same data')
        parser.add_argument('--segments', type=int, default=1,
                            help='Split the window into N walk-forward segments for per-window metrics')
        parser.add_argument('--min-confidence', type=float, default=None,
                            help='Override engine min_confidence (test a higher-confidence filter)')
        parser.add_argument('--exit-tp2', action='store_true',
                            help='Exit winners at TP2 instead of TP1 (let winners run)')
        parser.add_argument('--fee-rate', type=float, default=0.0004,
                            help='Per-side fee rate applied to turnover (taker 0.0004, maker ~0.0002)')
        parser.add_argument('--slippage-rate', type=float, default=0.0002,
                            help='Per-side slippage rate applied to turnover')
        parser.add_argument('--entry-tf', default=None, help='Override entry timeframe (e.g. 5m, 15m, 1h, 4h)')
        parser.add_argument('--trend-tf', default=None, help='Override trend timeframe (higher than entry)')

    def handle(self, *args, **options):
        end_ms = int(timezone.now().timestamp() * 1000)
        start_ms = end_ms - options['days'] * 86_400_000
        start_ts = timezone.datetime.utcfromtimestamp(start_ms / 1000)
        end_ts = timezone.datetime.utcfromtimestamp(end_ms / 1000)

        if options['compare']:
            self._run_compare(options, start_ms, end_ms, start_ts, end_ts)
            return

        cfg = _load_config()
        self._apply_overrides(cfg, options)
        symbols = self._resolve_symbols(options['symbols'], cfg)
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

    def _apply_overrides(self, cfg, options):
        """Apply experiment flags onto the engine config."""
        if options['structure_v3']:
            cfg.structure_quality_enabled = True
            cfg.structure_min_swing_atr = options['min_swing_atr']
            cfg.weight_structure_bonus = options['structure_bonus']
            cfg.require_bos = options['require_bos']
            cfg.block_on_choch = options['block_choch']
        if options['trend_filter']:
            cfg.trend_filter_enabled = True
            cfg.trend_min_slope_pct = options['trend_min_slope']
            cfg.trend_min_ema_gap_pct = options['trend_min_gap']
            cfg.trend_require_price_above_ema50 = options['trend_price_above']
            cfg.trend_require_adx_rising = options['trend_adx_rising']
        if options['regime_filter']:
            cfg.regime_filter_enabled = True
            cfg.regime_min_adx = options['regime_min_adx']
            cfg.regime_max_choppiness = options['regime_max_chop']
            cfg.regime_min_bbw_pct = options['regime_min_bbw']
            cfg.regime_atr_percentile_min = options['regime_atr_pct_min']
        if options.get('min_confidence') is not None:
            cfg.min_confidence = options['min_confidence']
        if options.get('entry_tf'):
            cfg.entry_timeframe = options['entry_tf']
        if options.get('trend_tf'):
            cfg.trend_timeframe = options['trend_tf']
        cfg.bt_exit_tp2 = options.get('exit_tp2', False)
        cfg.bt_fee_rate = options.get('fee_rate', 0.0004)
        cfg.bt_slippage_rate = options.get('slippage_rate', 0.0002)

    def _run_compare(self, options, start_ms, end_ms, start_ts, end_ts):
        """Run pure baseline vs the experiment config over the same fetched data."""
        base_cfg = _load_config()
        v3_cfg = _load_config()
        self._apply_overrides(v3_cfg, options)
        symbols = self._resolve_symbols(options['symbols'], base_cfg)
        base_engine = DayTradeSignalEngine(base_cfg)
        v3_engine = DayTradeSignalEngine(v3_cfg)

        self.stdout.write(
            f"Compare over {options['days']}d, {len(symbols)} symbol(s), {options['segments']} segment(s) | "
            f"structure={v3_cfg.structure_quality_enabled}(swing {v3_cfg.structure_min_swing_atr}, "
            f"bonus {v3_cfg.weight_structure_bonus}) | "
            f"trend={v3_cfg.trend_filter_enabled}(slope {v3_cfg.trend_min_slope_pct}, "
            f"gap {v3_cfg.trend_min_ema_gap_pct}, price>{v3_cfg.trend_require_price_above_ema50}, "
            f"adx_rising {v3_cfg.trend_require_adx_rising}) | "
            f"regime={v3_cfg.regime_filter_enabled}(adx {v3_cfg.regime_min_adx}, "
            f"chop {v3_cfg.regime_max_choppiness}, bbw {v3_cfg.regime_min_bbw_pct}, "
            f"atr_pct {v3_cfg.regime_atr_percentile_min})"
        )

        base_all, v3_all = [], []
        for symbol in symbols:
            self.stdout.write(f"  {symbol}: fetching + backtesting both...")
            df15, df1h = asyncio.run(
                _fetch_symbol_frames(symbol, start_ms, end_ms, base_cfg.entry_timeframe, base_cfg.trend_timeframe)
            )
            if df15 is None:
                self.stdout.write(self.style.WARNING(f"  {symbol}: no data, skipping"))
                continue
            base_all.extend(_backtest_symbol(base_engine, base_cfg, symbol, df15, df1h, start_ts))
            v3_all.extend(_backtest_symbol(v3_engine, v3_cfg, symbol, df15, df1h, start_ts))

        self._print_compare(base_cfg, v3_cfg, base_all, v3_all, start_ts, end_ts, options['segments'])

    def _print_compare(self, base_cfg, v3_cfg, base_all, v3_all, start_ts, end_ts, segments):
        """Print per-segment baseline-vs-V3 metrics plus a win tally."""
        base_buckets = _segment_trades(base_all, start_ts, end_ts, segments)
        v3_buckets = _segment_trades(v3_all, start_ts, end_ts, segments)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("==== Walk-forward compare (baseline vs V3) ===="))
        self.stdout.write(f"  {'segment':<10}{'base PF':>9}{'v3 PF':>9}{'base net':>11}{'v3 net':>10}{'  winner':>10}")
        v3_wins = 0
        for i in range(segments):
            b = _summarize(base_cfg, base_buckets[i])
            v = _summarize(v3_cfg, v3_buckets[i])
            winner = 'v3' if (v['profit_factor'] or 0) > (b['profit_factor'] or 0) else 'base'
            v3_wins += 1 if winner == 'v3' else 0
            self.stdout.write(
                f"  seg {i + 1:<6}{str(b['profit_factor']):>9}{str(v['profit_factor']):>9}"
                f"{b['net_pnl_usdt']:>11}{v['net_pnl_usdt']:>10}{winner:>10}"
            )
        bo = _summarize(base_cfg, base_all)
        vo = _summarize(v3_cfg, v3_all)
        self.stdout.write("")
        self.stdout.write(f"  OVERALL base: PF {bo['profit_factor']} net ${bo['net_pnl_usdt']} "
                          f"win {bo['win_rate']}% DD ${bo['max_drawdown_usdt']} maxConsecL {bo['max_consecutive_losses']}")
        self.stdout.write(f"  OVERALL v3:   PF {vo['profit_factor']} net ${vo['net_pnl_usdt']} "
                          f"win {vo['win_rate']}% DD ${vo['max_drawdown_usdt']} maxConsecL {vo['max_consecutive_losses']}")
        self.stdout.write(self.style.SUCCESS(f"  V3 wins {v3_wins}/{segments} segments on profit factor"))

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
