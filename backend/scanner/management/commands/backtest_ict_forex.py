"""Backtest the ICT order-block strategy on FOREX (Yahoo data, net-of-cost).

Reuses the crypto ICT strategy core (backtest_ict) but sources OHLC from Yahoo
Finance (keyless) so the same order-block logic can be tested on FX majors.
Entry frame = 1h resampled to 4h; trend frame = 1D. Forex has near-zero
centralized volume and much lower costs than crypto (spread ~1 pip ~ 0.01%),
so the default fee/slippage is far smaller than the crypto backtests.

Research only: no DB writes, no live orders.

Usage:
    python manage.py backtest_ict_forex --setup order_block --days 700
"""
import json
import urllib.request
from datetime import timedelta

import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone

from scanner.management.commands.backtest_ict import (
    _entries, _summarize, _segment_report, _trend_labels,
)

FX_MAJORS = ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X', 'USDCHF=X', 'NZDUSD=X']


def _yahoo(symbol, interval, rng):
    """Fetch a Yahoo Finance OHLCV frame (naive-UTC DatetimeIndex)."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval={interval}&range={rng}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    r = data['chart']['result'][0]
    ts = r['timestamp']
    q = r['indicators']['quote'][0]
    df = pd.DataFrame({
        'open': q['open'], 'high': q['high'], 'low': q['low'], 'close': q['close'],
        'volume': q.get('volume') or [0] * len(ts),
    }, index=pd.to_datetime(ts, unit='s'))
    return df.dropna(subset=['open', 'high', 'low', 'close'])


def _resample(df, rule):
    """Resample an OHLCV frame to a coarser bar (e.g. 1h -> 4h)."""
    out = df.resample(rule, origin='epoch').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    return out.dropna(subset=['open', 'high', 'low', 'close'])


class Command(BaseCommand):
    help = "Backtest the ICT order-block on forex majors (Yahoo data, net-of-cost)"

    def add_arguments(self, parser):
        parser.add_argument('--symbols', default=','.join(FX_MAJORS))
        parser.add_argument('--days', type=int, default=700)
        parser.add_argument('--setup', default='order_block',
                            choices=['order_block', 'sweep_mss_fvg', 'fvg_continuation'])
        parser.add_argument('--adx-min', type=float, default=20.0)
        parser.add_argument('--swing-k', type=int, default=2)
        parser.add_argument('--lookback', type=int, default=10)
        parser.add_argument('--pd-lookback', type=int, default=20)
        parser.add_argument('--rr', type=float, default=2.0)
        parser.add_argument('--sl-buffer-atr', type=float, default=0.25)
        parser.add_argument('--min-score', type=int, default=0)
        parser.add_argument('--trail-atr', type=float, default=0.0)
        parser.add_argument('--structure', default='any', choices=['any', 'bos', 'choch'])
        parser.add_argument('--fee-rate', type=float, default=0.00003, help='Per-side fee (forex ~ tiny)')
        parser.add_argument('--slippage-rate', type=float, default=0.00002)
        parser.add_argument('--margin', type=float, default=100.0)
        parser.add_argument('--leverage', type=float, default=10.0)
        parser.add_argument('--segments', type=int, default=1)

    def handle(self, *args, **options):
        start_ts = timezone.datetime.utcnow() - timedelta(days=options['days'])
        end_ts = timezone.datetime.utcnow()
        symbols = [s.strip().upper() for s in options['symbols'].split(',') if s.strip()]
        opts = {
            'adx_min': options['adx_min'], 'swing_k': options['swing_k'],
            'lookback': options['lookback'], 'pd_lb': options['pd_lookback'],
            'rr': options['rr'], 'sl_buffer_atr': options['sl_buffer_atr'],
            'fee': options['fee_rate'], 'slip': options['slippage_rate'],
            'notional': options['margin'] * options['leverage'], 'start_ts': start_ts,
            'structure': options['structure'], 'require_trend': False,
            'require_pd': False, 'min_score': options['min_score'],
            'trail_atr': options['trail_atr'], 'killzone': set(),
        }
        delta = timedelta(days=1)
        self.stdout.write(
            f"FOREX ICT | {len(symbols)} pairs | {options['days']}d | entry 4h(1h->4h) trend 1d | "
            f"setup {options['setup']} RR {opts['rr']} | net fee {opts['fee']}+slip {opts['slip']}"
        )

        all_trades = []
        for symbol in symbols:
            try:
                df1h = _yahoo(symbol, '1h', '730d')
                df1d = _yahoo(symbol, '1d', '5y')
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  {symbol}: fetch failed ({exc})"))
                continue
            df4h = _resample(df1h, '4h')
            if len(df4h) < 250 or len(df1d) < 220:
                self.stdout.write(self.style.WARNING(f"  {symbol}: insufficient data"))
                continue
            ctx = (df1d.index.values, _trend_labels(df1d, opts['adx_min']), delta)
            trades = _entries(options['setup'], symbol, df4h, ctx, opts)
            s = _summarize([t['pnl'] for t in trades])
            self.stdout.write(
                f"  {symbol:9s} trades={s.get('trades', 0):4d} win={s.get('win_rate', 0)}% "
                f"PF={s.get('profit_factor')} net=${s.get('net_pnl', 0)}"
            )
            all_trades.extend(trades)

        overall = _summarize([t['pnl'] for t in all_trades])
        self.stdout.write(
            f"  OVERALL   trades={overall.get('trades', 0):4d} win={overall.get('win_rate', 0)}% "
            f"PF={overall.get('profit_factor')} net=${overall.get('net_pnl', 0)} exp={overall.get('expectancy', 0)}"
        )
        if options['segments'] > 1:
            for label, seg in _segment_report(all_trades, start_ts, end_ts, options['segments']):
                self.stdout.write(f"      {label}: trades={seg.get('trades', 0):4d} "
                                  f"PF={seg.get('profit_factor')} net=${seg.get('net_pnl', 0)}")
