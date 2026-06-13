"""
End-to-end test: Signal generation -> Neutral reversal -> Binance order.

Runs the REAL signal engine against live Binance candle data, then optionally
places the generated signal as a futures order — the exact same flow as production.

Usage:
    python manage.py test_signal_to_order                                    # Scan BTCUSDT 1h
    python manage.py test_signal_to_order --scan-all --timeframe 15m,1h,4h   # Scan top 20 pairs
    python manage.py test_signal_to_order --debug                            # Show indicator values
    python manage.py test_signal_to_order --force-signal LONG                # Skip engine, use live price
    python manage.py test_signal_to_order --force-signal LONG --execute      # Force signal + real order
    python manage.py test_signal_to_order --execute --force                  # Engine signal + bypass checks
"""
import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand

from signals.models import Signal, Symbol, TradingSession
from signals.models.futures import FuturesTradingSettings, FuturesTrade
from signals.services.futures_trader import (
    BinanceFuturesTrader, futures_trading_service, _run_in_thread, NEPAL_TZ_OFFSET,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'End-to-end test: real signal engine scan -> Binance order placement'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', default='BTCUSDT', help='Symbol to scan (default: BTCUSDT)')
        parser.add_argument('--scan-all', action='store_true', help='Scan top 20 futures pairs by volume')
        parser.add_argument('--timeframe', default='1h', help='Comma-separated timeframes (default: 1h)')
        parser.add_argument('--execute', action='store_true', help='Place REAL order on Binance')
        parser.add_argument('--force', action='store_true', help='Bypass window/F&G/duplicate checks')
        parser.add_argument('--lower-confidence', type=float, default=None,
                            help='Override min_confidence for testing (e.g. 0.50)')
        parser.add_argument('--candles', type=int, default=200, help='Number of candles to fetch')
        parser.add_argument('--debug', action='store_true',
                            help='Show live indicator values to see why no signal generated')
        parser.add_argument('--force-signal', choices=['LONG', 'SHORT'], default=None,
                            help='Skip signal engine, create signal from live price with SL/TP from config')

    def handle(self, *args, **options):
        self.execute_order = options['execute']
        self.force = options['force']
        self.lower_confidence = options['lower_confidence']
        self.debug = options['debug']
        self.force_signal = options['force_signal']

        nepal_now = datetime.now(timezone.utc) + NEPAL_TZ_OFFSET
        self._header("SIGNAL-TO-ORDER END-TO-END TEST")
        self._info(f"Nepal Time: {nepal_now.strftime('%Y-%m-%d %H:%M:%S %A')} NPT")
        mode = 'FORCE EXECUTE' if self.force else 'EXECUTE' if self.execute_order else 'SCAN ONLY'
        if self.force_signal:
            mode = f"FORCE {self.force_signal} SIGNAL + {mode}"
        self._info(f"Mode: {mode}")

        timeframes = [tf.strip() for tf in options['timeframe'].split(',')]
        candle_limit = options['candles']

        symbols = self._resolve_symbols(options)
        if not symbols:
            return

        self._step_show_settings()

        if self.force_signal:
            sig = self._step_force_signal(symbols[0], timeframes[0])
            if not sig:
                return
            all_signals = [sig]
        else:
            all_signals = []
            for tf in timeframes:
                signals = self._step_scan_timeframe(symbols, tf, candle_limit)
                all_signals.extend(signals)

        if not all_signals:
            self._header("NO SIGNALS GENERATED")
            self._info("The signal engine found no setups meeting the criteria.")
            self._info("Suggestions:")
            self._info("  --debug                  Show indicator values")
            self._info("  --force-signal LONG      Create signal from live price (skip engine)")
            self._info("  --scan-all               Scan top 20 pairs")
            self._info("  --timeframe 15m,1h,4h    Try multiple timeframes")
            return

        self._header(f"GENERATED {len(all_signals)} SIGNAL(S)")
        for i, sig in enumerate(all_signals, 1):
            self._print_signal(i, sig)

        if not self.execute_order:
            self._header("SCAN COMPLETE (DRY RUN)")
            self._ok(f"Found {len(all_signals)} signal(s). Use --execute to place real orders.")
            return

        best = self._pick_best_signal(all_signals)
        self._header("SELECTED SIGNAL FOR EXECUTION")
        self._print_signal(1, best)

        self._confirm_execution(best)

        trade, db_signal = self._step_execute_signal(best)
        if trade and db_signal:
            self._step_verify_prices(trade, db_signal)

    def _resolve_symbols(self, options):
        """Get list of symbols to scan."""
        if options['scan_all']:
            self._header("FETCHING TOP FUTURES PAIRS")
            symbols = self._fetch_top_pairs(20)
            if symbols:
                self._ok(f"Top {len(symbols)} pairs by 24h volume")
                for chunk_start in range(0, len(symbols), 5):
                    chunk = symbols[chunk_start:chunk_start + 5]
                    self._info(f"  {', '.join(chunk)}")
            return symbols

        symbol = options['symbol'].upper()
        self._info(f"Target: {symbol}")
        return [symbol]

    def _fetch_top_pairs(self, top_n):
        """Fetch top futures pairs by volume from Binance."""
        from scanner.services.binance_futures_client import BinanceFuturesClient

        async def _fetch():
            async with BinanceFuturesClient() as client:
                pairs = await client.get_usdt_futures_pairs()
                volume_data = []
                for i in range(0, len(pairs), 50):
                    batch = pairs[i:i + 50]
                    tasks = [client.get_24h_ticker(s) for s in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for sym, res in zip(batch, results):
                        if isinstance(res, dict):
                            try:
                                vol = float(res.get('quoteVolume', 0))
                                volume_data.append((sym, vol))
                            except (ValueError, TypeError):
                                pass
                    await asyncio.sleep(0.3)
                volume_data.sort(key=lambda x: x[1], reverse=True)
                return [s for s, _ in volume_data[:top_n]]

        try:
            return _run_in_thread(_fetch, timeout=120)
        except Exception as e:
            self._fail(f"Failed to fetch pairs: {e}")
            return []

    def _step_show_settings(self):
        """Display current trading settings."""
        self._header("TRADING SETTINGS")
        settings = FuturesTradingSettings.get_settings()
        self._info(f"Futures enabled: {settings.is_enabled}")
        self._info(f"Leverage: {settings.leverage}x | Amount: ${settings.trade_amount}")
        self._info(f"F&G filter: {'ON' if settings.fear_greed_enabled else 'OFF'}")

        session = TradingSession.get_matching_session(datetime.now(timezone.utc) + NEPAL_TZ_OFFSET)
        if session:
            self._ok(f"In trading window: {session.name}")
        else:
            self._info("Outside trading window" + (" (--force bypasses)" if self.force else ""))

        open_count = FuturesTrade.objects.filter(status='OPEN').count()
        self._info(f"Open trades: {open_count}/{settings.max_concurrent_trades}")

    def _step_force_signal(self, symbol, timeframe):
        """Create a signal from live price + config SL/TP, bypassing the signal engine."""
        self._header(f"FORCE {self.force_signal} SIGNAL FROM LIVE PRICE")

        price = self._fetch_live_price(symbol)
        if not price:
            return None

        sl_pct, tp_pct = self._get_sl_tp_pct(timeframe)
        entry = price
        risk = Decimal(str(sl_pct)) / Decimal('100')
        profit = Decimal(str(tp_pct)) / Decimal('100')

        if self.force_signal == 'LONG':
            sl = entry * (1 - risk)
            tp = entry * (1 + profit)
        else:
            sl = entry * (1 + risk)
            tp = entry * (1 - profit)

        self._ok(f"Live price: ${price}")
        self._ok(f"Direction: {self.force_signal}")
        self._ok(f"Entry: ${entry}")
        self._ok(f"SL: ${sl} ({sl_pct}%)")
        self._ok(f"TP: ${tp} ({tp_pct}%)")
        rr = float(tp_pct) / float(sl_pct) if sl_pct else 0
        self._info(f"R/R: 1:{rr:.1f}")

        return {
            'symbol': symbol,
            'direction': self.force_signal,
            'entry': str(entry),
            'sl': str(sl),
            'tp': str(tp),
            'confidence': 0.80,
            'timeframe': timeframe,
            'market_type': 'FUTURES',
            'leverage': 10,
            '_forced': True,
        }

    def _fetch_live_price(self, symbol):
        """Fetch current price from Binance."""
        async def _fetch():
            trader = BinanceFuturesTrader(use_testnet=False)
            try:
                return await trader.get_current_price(symbol)
            finally:
                await trader.close()

        try:
            return _run_in_thread(_fetch)
        except Exception as e:
            self._fail(f"Failed to fetch price: {e}")
            return None

    def _get_sl_tp_pct(self, timeframe):
        """Get SL/TP percentages from DB config or defaults."""
        try:
            from signals.models.strategy_config import StrategyConfig
            db_config = StrategyConfig.get_config(timeframe)
            if db_config and db_config.is_active:
                return float(db_config.sl_percentage), float(db_config.tp_percentage)
        except Exception:
            pass
        return 2.5, 6.0

    def _step_scan_timeframe(self, symbols, timeframe, candle_limit):
        """Run the real signal engine on live candle data for one timeframe."""
        self._header(f"SCANNING {timeframe.upper()} TIMEFRAME ({len(symbols)} symbol(s))")

        config = self._load_config(timeframe)
        if not config:
            return []

        if self.lower_confidence is not None:
            original = config.min_confidence
            config.min_confidence = self.lower_confidence
            self._info(f"Confidence override: {original} -> {self.lower_confidence}")

        klines_data = self._fetch_klines(symbols, timeframe, candle_limit)
        if not klines_data:
            return []

        if self.debug:
            self._show_debug_indicators(klines_data, config, timeframe)

        return self._run_signal_engine(klines_data, config, timeframe)

    def _load_config(self, timeframe):
        """Load signal config from DB StrategyConfig or fall back to hardcoded defaults."""
        try:
            from signals.models.strategy_config import StrategyConfig
            db_config = StrategyConfig.get_config(timeframe)
            if db_config and db_config.is_active:
                config = db_config.to_signal_config()
                self._ok(f"Config loaded from DB: {timeframe} (SL={db_config.sl_percentage}%, TP={db_config.tp_percentage}%)")
                return config
            self._info(f"DB config for {timeframe} is inactive, using hardcoded defaults")
        except Exception as e:
            self._info(f"No DB config for {timeframe}: {e}")

        from scanner.tasks.futures_multi_timeframe_scanner import FUTURES_TIMEFRAME_CONFIGS
        config = FUTURES_TIMEFRAME_CONFIGS.get(timeframe)
        if config:
            self._ok(f"Config loaded from defaults: {timeframe}")
            return config

        self._fail(f"No config available for {timeframe}")
        return None

    def _fetch_klines(self, symbols, timeframe, limit):
        """Fetch live candle data from Binance Futures API."""
        from scanner.services.binance_futures_client import BinanceFuturesClient

        async def _fetch():
            async with BinanceFuturesClient() as client:
                return await client.batch_get_klines(
                    symbols, interval=timeframe, limit=limit, batch_size=5
                )

        try:
            data = _run_in_thread(_fetch, timeout=120)
            fetched = {s: k for s, k in data.items() if k and len(k) >= 50}
            self._ok(f"Fetched candles for {len(fetched)}/{len(symbols)} symbols ({limit} candles each)")
            skipped = len(symbols) - len(fetched)
            if skipped:
                self._info(f"Skipped {skipped} symbols (insufficient candle data)")
            return fetched
        except Exception as e:
            self._fail(f"Failed to fetch klines: {e}")
            return {}

    def _show_debug_indicators(self, klines_data, config, timeframe):
        """Show current indicator values for each symbol to diagnose why no signal fires."""
        from scanner.indicators.indicator_utils import klines_to_dataframe, calculate_all_indicators

        try:
            from signals.models.strategy_config import StrategyConfig
            db_config = StrategyConfig.get_config(timeframe)
        except Exception:
            db_config = None

        self._header("INDICATOR DEBUG")
        self._info(f"Config thresholds: RSI {config.long_rsi_min}-{config.long_rsi_max} (LONG), "
                    f"ADX >= {config.long_adx_min}, Conf >= {config.min_confidence}")

        for symbol, klines in klines_data.items():
            try:
                df = klines_to_dataframe(klines)
                df = calculate_all_indicators(df, config=db_config)
                cur = df.iloc[-1]
                prev = df.iloc[-2]

                price = cur['close']
                rsi = cur['rsi']
                adx = cur['adx']
                macd_h = cur['macd_hist']
                plus_di = cur['plus_di']
                minus_di = cur['minus_di']
                ema9 = cur['ema_9']
                ema21 = cur['ema_21']
                ema50 = cur['ema_50']
                vol = cur.get('volume_trend', 0)
                ha_bull = cur.get('ha_bullish', False)
                supertrend = cur.get('supertrend_direction', 0)
                mfi = cur.get('mfi', 0)
                psar_bull = cur.get('psar_bullish', False)
                bb_upper = cur.get('bb_upper', 0)
                bb_lower = cur.get('bb_lower', 0)

                rsi_long_ok = config.long_rsi_min < rsi < config.long_rsi_max
                rsi_short_ok = config.short_rsi_min < rsi < config.short_rsi_max
                adx_ok = adx > config.long_adx_min
                ema_aligned_bull = ema9 > ema21 > ema50
                ema_aligned_bear = ema9 < ema21 < ema50

                bb_range = bb_upper - bb_lower
                bb_pos = ((price - bb_lower) / bb_range * 100) if bb_range > 0 else 50

                self.stdout.write(f"\n  --- {symbol} @ ${price:.2f} ---")
                self._indicator("RSI", f"{rsi:.1f}", f"LONG zone {config.long_rsi_min}-{config.long_rsi_max}", rsi_long_ok)
                self._indicator("RSI", f"{rsi:.1f}", f"SHORT zone {config.short_rsi_min}-{config.short_rsi_max}", rsi_short_ok)
                self._indicator("ADX", f"{adx:.1f}", f">= {config.long_adx_min}", adx_ok)
                self._indicator("MACD hist", f"{macd_h:.4f}", "rising" if macd_h > prev['macd_hist'] else "falling", macd_h > 0)
                self._indicator("+DI/-DI", f"{plus_di:.1f}/{minus_di:.1f}", "+DI > -DI", plus_di > minus_di)
                self._indicator("EMA align", f"9>{ema9:.0f} 21>{ema21:.0f} 50>{ema50:.0f}",
                                "bullish" if ema_aligned_bull else ("bearish" if ema_aligned_bear else "mixed"),
                                ema_aligned_bull or ema_aligned_bear)
                self._indicator("SuperTrend", "BULL" if supertrend == 1 else "BEAR", "", supertrend == 1)
                self._indicator("Heikin Ashi", "BULL" if ha_bull else "BEAR", "", ha_bull)
                self._indicator("PSAR", "BULL" if psar_bull else "BEAR", "", psar_bull)
                self._indicator("MFI", f"{mfi:.1f}", "20-50 = LONG zone", 20 < mfi < 50)
                self._indicator("Volume", f"{vol:.2f}x", "> 1.0x avg", vol > 1.0)
                self._indicator("BB pos", f"{bb_pos:.0f}%", "< 25% = LONG zone", bb_pos < 25)

                bullish_count = sum([
                    supertrend == 1, plus_di > minus_di, ema_aligned_bull, ha_bull, psar_bull
                ])
                bearish_count = sum([
                    supertrend != 1, minus_di > plus_di, ema_aligned_bear, not ha_bull, not psar_bull
                ])
                self._info(f"  Bullish confirmations: {bullish_count}/5 (need 3+)")
                self._info(f"  Bearish confirmations: {bearish_count}/5 (need 3+)")

            except Exception as e:
                self._fail(f"  {symbol}: Debug error - {e}")

    def _indicator(self, name, value, condition, passed):
        """Print a single indicator with pass/fail."""
        mark = self.style.SUCCESS("PASS") if passed else self.style.ERROR("FAIL")
        self.stdout.write(f"  {mark}  {name:15s} = {value:20s}  ({condition})")

    def _run_signal_engine(self, klines_data, config, timeframe):
        """Run SignalDetectionEngine on fetched candle data."""
        from scanner.strategies.signal_engine import SignalDetectionEngine

        try:
            from signals.models.strategy_config import StrategyConfig
            db_config = StrategyConfig.get_config(timeframe)
        except Exception:
            db_config = None

        engine = SignalDetectionEngine(
            config=config,
            use_volatility_aware=False,
            db_config=db_config
        )

        signals = []
        for symbol, klines in klines_data.items():
            try:
                engine.update_candles(symbol, klines)
                result = engine.process_symbol(symbol, timeframe)

                if result and result.get('action') == 'created':
                    signal_data = result['signal']
                    signal_data['timeframe'] = timeframe
                    signal_data['market_type'] = 'FUTURES'
                    signal_data['leverage'] = 10
                    signals.append(signal_data)
                    self._ok(f"  {symbol}: {signal_data.get('direction')} @ ${signal_data.get('entry', signal_data.get('entry_price', '?'))} "
                             f"(Conf: {signal_data['confidence']:.0%})")
            except Exception as e:
                self._fail(f"  {symbol}: Error - {e}")

        if not signals:
            self._info("  No signals generated for this timeframe")

        return signals

    def _print_signal(self, index, sig):
        """Display a signal's details."""
        symbol = sig.get('symbol', '?')
        direction = sig.get('direction', sig.get('signal_type', '?'))
        entry = sig.get('entry', sig.get('entry_price', '?'))
        sl = sig.get('sl', sig.get('stop_loss', '?'))
        tp = sig.get('tp', sig.get('take_profit', '?'))
        conf = sig.get('confidence', 0)
        tf = sig.get('timeframe', '?')
        forced = " [FORCED]" if sig.get('_forced') else ""

        self._ok(f"  #{index} {direction} {symbol} ({tf}){forced}")
        self._info(f"     Entry: ${entry}")
        self._info(f"     SL:    ${sl}")
        self._info(f"     TP:    ${tp}")
        self._info(f"     Confidence: {conf:.0%}")

    def _pick_best_signal(self, signals):
        """Pick the highest-confidence signal for execution."""
        return max(signals, key=lambda s: s.get('confidence', 0))

    def _confirm_execution(self, sig):
        """Prompt user before placing real order."""
        direction = sig.get('direction', sig.get('signal_type'))
        symbol = sig.get('symbol')
        entry = sig.get('entry', sig.get('entry_price'))
        self.stdout.write(self.style.WARNING(
            f"\n  *** REAL MONEY — PLACING FUTURES ORDER ***\n"
            f"  {direction} {symbol} @ ~${entry}\n"
        ))
        confirm = input("  Type 'YES' to confirm: ")
        if confirm != 'YES':
            self.stdout.write("  Cancelled.")
            raise SystemExit(0)

    def _step_execute_signal(self, sig):
        """Save signal to DB and execute via futures_trading_service."""
        self._header("EXECUTING: SAVE SIGNAL -> BINANCE ORDER")

        symbol_name = sig.get('symbol')
        direction = sig.get('direction', sig.get('signal_type'))
        entry = Decimal(str(sig.get('entry', sig.get('entry_price'))))
        raw_sl = Decimal(str(sig.get('sl', sig.get('stop_loss'))))
        raw_tp = Decimal(str(sig.get('tp', sig.get('take_profit'))))
        confidence = sig.get('confidence', 0.80)
        timeframe = sig.get('timeframe', '1h')

        final_dir, final_sl, final_tp, neutral_meta = self._apply_neutral_reversal(
            direction, entry, raw_sl, raw_tp
        )

        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=symbol_name, defaults={'market_type': 'FUTURES'}
        )

        from django.db.models.signals import post_save
        from signals.signals_handlers import execute_futures_trade_on_signal
        post_save.disconnect(execute_futures_trade_on_signal, sender=Signal)
        self._info("Disconnected signal handler to prevent double execution")

        try:
            signal = Signal(
                symbol=symbol_obj,
                timeframe=timeframe,
                direction=final_dir,
                confidence=confidence,
                entry=entry,
                sl=final_sl,
                tp=final_tp,
                status='ACTIVE',
                market_type='FUTURES',
                leverage=10,
                meta={'test_signal_to_order': True, 'source': 'management_command'},
            )
            signal.is_priority = True
            signal.save()

            if neutral_meta:
                signal.meta = {**(signal.meta or {}), **neutral_meta}
                signal.save(update_fields=['meta'])

            self._ok(f"Signal #{signal.id} saved to DB (is_priority=True)")
            self._info(f"  {signal.direction} {symbol_name} @ ${signal.entry}")
            self._info(f"  SL: ${signal.sl} | TP: ${signal.tp} | Conf: {signal.confidence:.0%}")
            if neutral_meta:
                self._info(f"  Neutral reversal applied (F&G={neutral_meta['neutral_reversal']['fg_value']})")

            self._info("Calling futures_trading_service.execute_signal(force_execute=True)...")
            trade = futures_trading_service.execute_signal(signal, force_execute=True)

            if trade:
                self._report_trade(trade)
            else:
                self._fail("execute_signal returned None — check logs for reason")
                self._info(f"  Signal ID: {signal.id}")

            return trade, signal

        except Exception as e:
            self._fail(f"Execution error: {e}")
            import traceback
            traceback.print_exc()
            return None, None

        finally:
            post_save.connect(execute_futures_trade_on_signal, sender=Signal)

    def _apply_neutral_reversal(self, direction, entry, sl, tp):
        """Apply neutral market reversal if F&G is in neutral zone."""
        try:
            from scanner.services.neutral_reversal import apply_neutral_reversal
            final_dir, final_sl, final_tp, meta = apply_neutral_reversal(
                direction, entry, sl, tp, market_type='FUTURES'
            )
            if meta:
                nr = meta['neutral_reversal']
                self._info(f"Neutral reversal: {nr['original_direction']} -> {nr['final_direction']} "
                           f"(F&G={nr['fg_value']})")
            return final_dir, final_sl, final_tp, meta
        except Exception as e:
            self._info(f"Neutral reversal skipped: {e}")
            return direction, sl, tp, None

    def _report_trade(self, trade):
        """Display trade execution results."""
        self._header("TRADE PLACED ON BINANCE")
        self._ok(f"Trade #{trade.id}")
        self._ok(f"  {trade.direction} {trade.symbol} @ ${trade.entry_price}")
        self._ok(f"  Quantity: {trade.quantity} | Leverage: {trade.leverage}x")
        self._ok(f"  SL: ${trade.stop_loss} | TP: ${trade.take_profit}")
        self._ok(f"  Entry Order:  {trade.binance_order_id}")
        self._ok(f"  SL Order:     {trade.sl_order_id}")
        self._ok(f"  TP Order:     {trade.tp_order_id}")
        if trade.error_message:
            self._fail(f"  Warnings: {trade.error_message}")

    def _step_verify_prices(self, trade, db_signal):
        """Verify Binance order used the signal's exact EP/SL/TP (after neutral reversal)."""
        self._header("PRICE VERIFICATION")

        expected_entry = Decimal(str(db_signal.entry))
        expected_sl = Decimal(str(db_signal.sl))
        expected_tp = Decimal(str(db_signal.tp))

        self._info("Signal in DB (after neutral reversal):")
        self._info(f"  Entry: ${expected_entry} | SL: ${expected_sl} | TP: ${expected_tp}")
        self._info("Binance order:")
        self._info(f"  Entry: ${trade.entry_price} | SL: ${trade.stop_loss} | TP: ${trade.take_profit}")

        entry_ok = self._price_matches(expected_entry, trade.entry_price, Decimal('0.5'))
        sl_ok = self._price_matches(expected_sl, trade.stop_loss, Decimal('0.1'))
        tp_ok = self._price_matches(expected_tp, trade.take_profit, Decimal('0.1'))

        self._check("Entry matches signal (within 0.5% for LIMIT fill)", entry_ok)
        self._check("SL matches signal (tick-size rounded only)", sl_ok)
        self._check("TP matches signal (tick-size rounded only)", tp_ok)

        if entry_ok and sl_ok and tp_ok:
            self._ok("ALL PRICES VERIFIED — signal values used correctly")
        else:
            self._fail("PRICE MISMATCH — check for recalculation bugs in futures_trader.py")

    def _price_matches(self, expected, actual, tolerance_pct):
        """Check if two prices match within a tolerance percentage."""
        expected = Decimal(str(expected))
        actual = Decimal(str(actual))
        if expected == 0:
            return actual == 0
        diff_pct = abs(expected - actual) / expected * 100
        return diff_pct <= tolerance_pct

    def _check(self, label, passed):
        if passed:
            self._ok(label)
        else:
            self._fail(label)

    def _header(self, text):
        self.stdout.write(f"\n{'=' * 64}")
        self.stdout.write(f"  {text}")
        self.stdout.write(f"{'=' * 64}")

    def _ok(self, text):
        self.stdout.write(self.style.SUCCESS(f"  [OK] {text}"))

    def _fail(self, text):
        self.stdout.write(self.style.ERROR(f"  [FAIL] {text}"))

    def _info(self, text):
        self.stdout.write(f"  [..] {text}")
