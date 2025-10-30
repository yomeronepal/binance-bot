"""
Django management command to analyze paper trades and diagnose trading parameters.
Provides insights on TP/SL distances, win rates, and parameter recommendations.

Usage:
    python manage.py analyze_trades
    python manage.py analyze_trades --limit 20
    python manage.py analyze_trades --status CLOSED
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count, Q
from signals.models import PaperTrade, Signal
from datetime import datetime, timedelta
import sys


class Command(BaseCommand):
    help = 'Analyze paper trades and provide trading parameter recommendations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of sample trades to display (default: 10)'
        )
        parser.add_argument(
            '--status',
            type=str,
            default='OPEN',
            choices=['OPEN', 'CLOSED', 'CANCELLED', 'ALL'],
            help='Trade status to analyze (default: OPEN)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Analyze trades from last N days (optional)'
        )
        parser.add_argument(
            '--symbol',
            type=str,
            default=None,
            help='Filter by specific symbol (optional)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        status = options['status']
        days = options['days']
        symbol = options['symbol']

        # Build query
        query = Q()
        if status != 'ALL':
            query &= Q(status=status)
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            query &= Q(entry_time__gte=cutoff_date)
        if symbol:
            query &= Q(symbol=symbol)

        # Get trades
        trades = PaperTrade.objects.filter(query).order_by('-entry_time')
        total_count = trades.count()

        if total_count == 0:
            self.stdout.write(self.style.WARNING(f'\nNo trades found with status={status}'))
            return

        # Display header
        self.print_header('PAPER TRADE ANALYSIS')

        # Overall statistics
        self.stdout.write(self.style.SUCCESS('\n📊 OVERALL STATISTICS'))
        self.stdout.write(f"  Total trades analyzed: {total_count}")

        if status == 'ALL' or not status:
            open_count = PaperTrade.objects.filter(status='OPEN').count()
            closed_count = PaperTrade.objects.filter(status='CLOSED').count()
            cancelled_count = PaperTrade.objects.filter(status='CANCELLED').count()

            self.stdout.write(f"  • Open: {open_count}")
            self.stdout.write(f"  • Closed: {closed_count}")
            self.stdout.write(f"  • Cancelled: {cancelled_count}")

        if days:
            self.stdout.write(f"  Time period: Last {days} days")
        if symbol:
            self.stdout.write(f"  Symbol filter: {symbol}")

        # Sample trades
        sample_trades = list(trades[:limit])

        if sample_trades:
            self.stdout.write(self.style.SUCCESS(f'\n📋 SAMPLE TRADES (showing {len(sample_trades)} of {total_count})'))
            self.print_trades_table(sample_trades)

        # Calculate statistics
        self.analyze_tp_sl_distances(trades, status)

        # Analyze closed trades performance
        if status in ['CLOSED', 'ALL']:
            self.analyze_closed_trades_performance()

        # Check signal engine parameters
        self.check_signal_engine_parameters()

        # Recommendations
        self.print_recommendations(status)

    def print_header(self, title):
        """Print section header"""
        width = 80
        self.stdout.write('\n' + '=' * width)
        self.stdout.write(self.style.SUCCESS(title.center(width)))
        self.stdout.write('=' * width)

    def print_trades_table(self, trades):
        """Print formatted table of trades"""
        # Header
        header = f"{'Symbol':<12} {'Dir':<6} {'Entry':>12} {'TP':>12} {'SL':>12} {'TP%':>8} {'SL%':>8} {'R/R':>6}"
        self.stdout.write(header)
        self.stdout.write('-' * 80)

        # Rows
        for trade in trades:
            entry = float(trade.entry_price)
            tp = float(trade.take_profit)
            sl = float(trade.stop_loss)

            if trade.direction == 'LONG':
                tp_pct = ((tp - entry) / entry * 100)
                sl_pct = ((entry - sl) / entry * 100)
            else:  # SHORT
                tp_pct = ((entry - tp) / entry * 100)
                sl_pct = ((sl - entry) / entry * 100)

            rr_ratio = tp_pct / sl_pct if sl_pct > 0 else 0

            row = f"{trade.symbol:<12} {trade.direction:<6} ${entry:>11.2f} ${tp:>11.2f} ${sl:>11.2f} {tp_pct:>7.2f}% {sl_pct:>7.2f}% {rr_ratio:>5.2f}"
            self.stdout.write(row)

    def analyze_tp_sl_distances(self, trades, status):
        """Analyze TP/SL distance statistics"""
        self.stdout.write(self.style.SUCCESS('\n📏 TP/SL DISTANCE ANALYSIS'))

        # Calculate stats for each direction
        for direction in ['LONG', 'SHORT']:
            direction_trades = trades.filter(direction=direction)
            count = direction_trades.count()

            if count == 0:
                continue

            self.stdout.write(f"\n{direction} Trades ({count} total):")

            tp_distances = []
            sl_distances = []

            for trade in direction_trades:
                entry = float(trade.entry_price)
                tp = float(trade.take_profit)
                sl = float(trade.stop_loss)

                if direction == 'LONG':
                    tp_pct = ((tp - entry) / entry * 100)
                    sl_pct = ((entry - sl) / entry * 100)
                else:
                    tp_pct = ((entry - tp) / entry * 100)
                    sl_pct = ((sl - entry) / entry * 100)

                tp_distances.append(tp_pct)
                sl_distances.append(sl_pct)

            avg_tp = sum(tp_distances) / len(tp_distances)
            avg_sl = sum(sl_distances) / len(sl_distances)
            avg_rr = avg_tp / avg_sl if avg_sl > 0 else 0

            self.stdout.write(f"  Average TP distance: {avg_tp:.2f}%")
            self.stdout.write(f"  Average SL distance: {avg_sl:.2f}%")
            self.stdout.write(f"  Risk/Reward Ratio: 1:{avg_rr:.2f}")

            # Diagnosis
            self.diagnose_tp_sl(avg_tp, avg_sl, direction)

    def diagnose_tp_sl(self, avg_tp, avg_sl, direction):
        """Diagnose TP/SL settings and provide recommendations"""
        self.stdout.write(f"\n  🔍 DIAGNOSIS for {direction}:")

        # Check TP
        if avg_tp > 5:
            self.stdout.write(self.style.ERROR(f"    ⚠️  PROBLEM: TP targets are TOO FAR ({avg_tp:.1f}%)"))
            self.stdout.write("       No trades hitting TP because targets are unrealistic")
            self.stdout.write("       Recommendation: Reduce tp_atr_multiplier to 1.5-2.5")
        elif avg_tp > 3:
            self.stdout.write(self.style.WARNING(f"    ⚠️  TP targets are somewhat far ({avg_tp:.1f}%)"))
            self.stdout.write("       Consider reducing slightly for faster wins")
        else:
            self.stdout.write(self.style.SUCCESS(f"    ✅ TP targets look reasonable ({avg_tp:.1f}%)"))

        # Check SL
        if avg_sl > 4:
            self.stdout.write(self.style.ERROR(f"    ⚠️  PROBLEM: SL targets are TOO FAR ({avg_sl:.1f}%)"))
            self.stdout.write("       Giving market too much room, risking large losses")
            self.stdout.write("       Recommendation: Reduce sl_atr_multiplier to 1.0-1.5")
        elif avg_sl > 2.5:
            self.stdout.write(self.style.WARNING(f"    ⚠️  SL targets are somewhat wide ({avg_sl:.1f}%)"))
            self.stdout.write("       Consider tightening for better risk management")
        else:
            self.stdout.write(self.style.SUCCESS(f"    ✅ SL targets look reasonable ({avg_sl:.1f}%)"))

    def analyze_closed_trades_performance(self):
        """Analyze performance of closed trades"""
        closed_trades = PaperTrade.objects.filter(status='CLOSED')
        count = closed_trades.count()

        if count == 0:
            return

        self.stdout.write(self.style.SUCCESS(f'\n💰 CLOSED TRADES PERFORMANCE ({count} trades)'))

        # Calculate win rate
        winning_trades = closed_trades.filter(profit_loss__gt=0).count()
        losing_trades = closed_trades.filter(profit_loss__lte=0).count()
        win_rate = (winning_trades / count * 100) if count > 0 else 0

        # Calculate total P&L
        total_pnl = sum(float(t.profit_loss) for t in closed_trades if t.profit_loss)
        avg_pnl = total_pnl / count if count > 0 else 0

        # Calculate average profit and loss
        winning = [float(t.profit_loss) for t in closed_trades if t.profit_loss and t.profit_loss > 0]
        losing = [float(t.profit_loss) for t in closed_trades if t.profit_loss and t.profit_loss <= 0]

        avg_win = sum(winning) / len(winning) if winning else 0
        avg_loss = sum(losing) / len(losing) if losing else 0

        # Calculate profit factor
        total_wins = sum(winning) if winning else 0
        total_losses = abs(sum(losing)) if losing else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Display metrics
        self.stdout.write(f"  Win Rate: {win_rate:.1f}% ({winning_trades}W / {losing_trades}L)")
        self.stdout.write(f"  Total P&L: ${total_pnl:,.2f}")
        self.stdout.write(f"  Average P&L per trade: ${avg_pnl:,.2f}")
        self.stdout.write(f"  Average Win: ${avg_win:,.2f}")
        self.stdout.write(f"  Average Loss: ${avg_loss:,.2f}")
        self.stdout.write(f"  Profit Factor: {profit_factor:.2f}")

        # Performance assessment
        self.stdout.write("\n  📈 PERFORMANCE ASSESSMENT:")
        if win_rate >= 60:
            self.stdout.write(self.style.SUCCESS(f"    ✅ Excellent win rate ({win_rate:.1f}%)"))
        elif win_rate >= 50:
            self.stdout.write(self.style.SUCCESS(f"    ✅ Good win rate ({win_rate:.1f}%)"))
        elif win_rate >= 40:
            self.stdout.write(self.style.WARNING(f"    ⚠️  Average win rate ({win_rate:.1f}%)"))
        else:
            self.stdout.write(self.style.ERROR(f"    ❌ Poor win rate ({win_rate:.1f}%)"))

        if profit_factor >= 2.0:
            self.stdout.write(self.style.SUCCESS(f"    ✅ Excellent profit factor ({profit_factor:.2f})"))
        elif profit_factor >= 1.5:
            self.stdout.write(self.style.SUCCESS(f"    ✅ Good profit factor ({profit_factor:.2f})"))
        elif profit_factor >= 1.0:
            self.stdout.write(self.style.WARNING(f"    ⚠️  Breakeven profit factor ({profit_factor:.2f})"))
        else:
            self.stdout.write(self.style.ERROR(f"    ❌ Losing strategy ({profit_factor:.2f})"))

    def check_signal_engine_parameters(self):
        """Check current signal engine parameters"""
        self.stdout.write(self.style.SUCCESS('\n⚙️  CURRENT SIGNAL ENGINE PARAMETERS'))

        try:
            from scanner.strategies.signal_engine import SignalConfig

            config = SignalConfig()

            self.stdout.write(f"\n  📋 Default Configuration:")
            self.stdout.write(f"     LONG RSI Range: {config.long_rsi_min} - {config.long_rsi_max}")
            self.stdout.write(f"     SHORT RSI Range: {config.short_rsi_min} - {config.short_rsi_max}")
            self.stdout.write(f"     ADX Minimum (LONG): {config.long_adx_min}")
            self.stdout.write(f"     ADX Minimum (SHORT): {config.short_adx_min}")
            self.stdout.write(f"     SL ATR Multiplier: {config.sl_atr_multiplier}x")
            self.stdout.write(f"     TP ATR Multiplier: {config.tp_atr_multiplier}x")
            self.stdout.write(f"     Min Confidence: {config.min_confidence:.0%}")
            self.stdout.write(f"     Volume Multiplier: {config.long_volume_multiplier}x")

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Could not import SignalConfig: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Error reading parameters: {e}"))

    def print_recommendations(self, status):
        """Print actionable recommendations"""
        self.print_header('RECOMMENDED ACTIONS')

        if status == 'OPEN':
            open_count = PaperTrade.objects.filter(status='OPEN').count()

            if open_count > 50:
                self.stdout.write(self.style.WARNING(
                    f"\n⚠️  You have {open_count} open trades - TP/SL might need adjustment\n"
                ))

            self.stdout.write("1️⃣  IMMEDIATE FIX - Adjust TP/SL in SignalConfig:")
            self.stdout.write("   • Edit: backend/scanner/strategies/signal_engine.py")
            self.stdout.write("   • Reduce tp_atr_multiplier to 1.5-2.5 (for faster wins)")
            self.stdout.write("   • Reduce sl_atr_multiplier to 1.0-1.5 (tighter risk control)")
            self.stdout.write("   • This allows trades to close and generate performance data")

            self.stdout.write("\n2️⃣  RESTART SERVICES:")
            self.stdout.write("   docker-compose restart backend celery-worker")

            self.stdout.write("\n3️⃣  WAIT FOR TRADES TO CLOSE:")
            self.stdout.write("   • Let 50-100 trades close with new parameters")
            self.stdout.write("   • Then run: python manage.py analyze_trades --status CLOSED")

        elif status == 'CLOSED':
            closed_count = PaperTrade.objects.filter(status='CLOSED').count()

            if closed_count >= 50:
                self.stdout.write(self.style.SUCCESS(
                    f"\n✅ You have {closed_count} closed trades - ready for ML optimization!\n"
                ))

                self.stdout.write("1️⃣  RUN ML TUNING FOR OPTIMIZATION:")
                self.stdout.write("   • Trigger via API: POST /api/mltuning/")
                self.stdout.write("   • Or use test script: ./test_mltuning.sh")
                self.stdout.write("   • ML will find optimal TP/SL and other parameters")

                self.stdout.write("\n2️⃣  RUN WALK-FORWARD OPTIMIZATION:")
                self.stdout.write("   • POST /api/walkforward/")
                self.stdout.write("   • Validates strategy on out-of-sample data")

                self.stdout.write("\n3️⃣  RUN MONTE CARLO SIMULATION:")
                self.stdout.write("   • POST /api/montecarlo/")
                self.stdout.write("   • Tests strategy robustness under various scenarios")

            else:
                self.stdout.write(f"\n📊 You have {closed_count} closed trades")
                self.stdout.write("   • Need at least 50 closed trades for reliable ML tuning")
                self.stdout.write("   • Keep trading and come back when you have more data")

        self.stdout.write("\n4️⃣  MONITOR LEARNING SYSTEM:")
        self.stdout.write("   • Check trade counters: python manage.py shell -c \"")
        self.stdout.write("     from signals.models_optimization import TradeCounter;")
        self.stdout.write("     for c in TradeCounter.objects.all(): print(f'{c.volatility_level}: {c.trade_count}/{c.threshold}')\"")

        self.stdout.write("\n5️⃣  TRIGGER MANUAL OPTIMIZATION:")
        self.stdout.write("   • curl -X POST http://localhost:8000/api/learning/optimize/ \\")
        self.stdout.write("       -H 'Authorization: Bearer TOKEN' \\")
        self.stdout.write("       -d '{\"volatility_level\": \"HIGH\", \"lookback_days\": 30}'")

        self.stdout.write("\n")
