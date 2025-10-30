"""
Django management command to analyze paper trading performance and signals
Provides comprehensive performance metrics, signal statistics, and recommendations
"""
from django.core.management.base import BaseCommand
from signals.models import PaperTrade, Signal
from django.db.models import Avg, Count, Sum, Q, Max, Min
from decimal import Decimal


class Command(BaseCommand):
    help = 'Analyze paper trading performance and signal generation with recommendations'

    def handle(self, *args, **options):
        """Main command handler"""
        self.analyze_paper_trades()
        self.analyze_signals()
        self.get_signal_engine_config()
        self.provide_recommendations()

    def analyze_paper_trades(self):
        """Analyze paper trading performance"""
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("PAPER TRADING PERFORMANCE ANALYSIS"))
        self.stdout.write("=" * 60)
        self.stdout.write("")

        # Get paper trade statistics
        total_trades = PaperTrade.objects.count()
        closed_trades = PaperTrade.objects.filter(status='CLOSED').count()
        open_trades = PaperTrade.objects.filter(status='OPEN').count()
        winning_trades = PaperTrade.objects.filter(status='CLOSED', profit_loss__gt=0).count()
        losing_trades = PaperTrade.objects.filter(status='CLOSED', profit_loss__lt=0).count()
        breakeven_trades = PaperTrade.objects.filter(status='CLOSED', profit_loss=0).count()

        win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0

        # Get PnL statistics
        avg_win = PaperTrade.objects.filter(status='CLOSED', profit_loss__gt=0).aggregate(avg=Avg('profit_loss'))['avg'] or Decimal('0')
        avg_loss = PaperTrade.objects.filter(status='CLOSED', profit_loss__lt=0).aggregate(avg=Avg('profit_loss'))['avg'] or Decimal('0')
        max_win = PaperTrade.objects.filter(status='CLOSED').aggregate(max=Max('profit_loss'))['max'] or Decimal('0')
        max_loss = PaperTrade.objects.filter(status='CLOSED').aggregate(min=Min('profit_loss'))['min'] or Decimal('0')
        total_pnl = PaperTrade.objects.filter(status='CLOSED').aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')

        self.stdout.write("TRADE STATISTICS:")
        self.stdout.write(f"  Total Trades:      {total_trades}")
        self.stdout.write(f"  Closed Trades:     {closed_trades}")
        self.stdout.write(f"  Open Trades:       {open_trades}")
        if closed_trades > 0:
            self.stdout.write(f"  Winning Trades:    {winning_trades} ({winning_trades/closed_trades*100:.1f}%)")
            self.stdout.write(f"  Losing Trades:     {losing_trades} ({losing_trades/closed_trades*100:.1f}%)")
        else:
            self.stdout.write("  Winning Trades:    0")
            self.stdout.write("  Losing Trades:     0")
        self.stdout.write(f"  Breakeven Trades:  {breakeven_trades}")
        self.stdout.write("")

        self.stdout.write("PERFORMANCE METRICS:")
        self.stdout.write(f"  Win Rate:          {win_rate:.2f}%")
        self.stdout.write(f"  Average Win:       ${float(avg_win):.2f}")
        self.stdout.write(f"  Average Loss:      ${float(avg_loss):.2f}")
        self.stdout.write(f"  Max Win:           ${float(max_win):.2f}")
        self.stdout.write(f"  Max Loss:          ${float(max_loss):.2f}")
        self.stdout.write(f"  Total PnL:         ${float(total_pnl):.2f}")

        if losing_trades > 0 and float(avg_loss) != 0:
            profit_factor = abs(float(avg_win) * winning_trades / (float(avg_loss) * losing_trades))
            self.stdout.write(f"  Profit Factor:     {profit_factor:.2f}")

            # Risk/Reward Ratio
            risk_reward = abs(float(avg_win) / float(avg_loss))
            self.stdout.write(f"  Risk/Reward Ratio: 1:{risk_reward:.2f}")

            # Expectancy
            expectancy = (win_rate/100 * float(avg_win)) - ((100-win_rate)/100 * abs(float(avg_loss)))
            self.stdout.write(f"  Expectancy:        ${expectancy:.2f} per trade")
        self.stdout.write("")

        # Analyze by direction
        self.stdout.write("BY DIRECTION:")
        long_trades = PaperTrade.objects.filter(status='CLOSED', direction='LONG')
        short_trades = PaperTrade.objects.filter(status='CLOSED', direction='SHORT')

        long_count = long_trades.count()
        short_count = short_trades.count()

        if long_count > 0:
            long_wins = long_trades.filter(profit_loss__gt=0).count()
            long_win_rate = (long_wins / long_count * 100)
            long_pnl = long_trades.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
            self.stdout.write(f"  LONG Trades:  {long_count} trades, {long_win_rate:.1f}% win rate, ${float(long_pnl):.2f} PnL")
        else:
            self.stdout.write("  LONG Trades:  0 trades")

        if short_count > 0:
            short_wins = short_trades.filter(profit_loss__gt=0).count()
            short_win_rate = (short_wins / short_count * 100)
            short_pnl = short_trades.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
            self.stdout.write(f"  SHORT Trades: {short_count} trades, {short_win_rate:.1f}% win rate, ${float(short_pnl):.2f} PnL")
        else:
            self.stdout.write("  SHORT Trades: 0 trades")
        self.stdout.write("")

        # Analyze by symbol
        self.stdout.write("TOP 5 SYMBOLS BY TRADE COUNT:")
        symbol_stats = PaperTrade.objects.filter(status='CLOSED').values('symbol').annotate(
            count=Count('id'),
            wins=Count('id', filter=Q(profit_loss__gt=0)),
            total_pnl=Sum('profit_loss')
        ).order_by('-count')[:5]

        for stat in symbol_stats:
            win_rate_sym = (stat['wins'] / stat['count'] * 100) if stat['count'] > 0 else 0
            self.stdout.write(f"  {stat['symbol']:10s}: {stat['count']:3d} trades, {win_rate_sym:5.1f}% win rate, ${float(stat['total_pnl'] or 0):8.2f} PnL")

        if symbol_stats.count() == 0:
            self.stdout.write("  No closed trades yet")
        self.stdout.write("")

        # Recent performance
        recent_trades = PaperTrade.objects.filter(
            status='CLOSED'
        ).order_by('-exit_time')[:20]

        if recent_trades.exists():
            self.stdout.write("LAST 20 CLOSED TRADES:")
            self.stdout.write(f"  {'Symbol':<10} {'Direction':<6} {'PnL':>10} {'Entry':>10} {'Exit':>10} {'Status'}")
            self.stdout.write(f"  {'-'*10} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
            for trade in recent_trades:
                pnl_str = f"${float(trade.profit_loss):.2f}"
                result = "WIN" if trade.profit_loss > 0 else "LOSS" if trade.profit_loss < 0 else "BE"
                self.stdout.write(f"  {trade.symbol:<10} {trade.direction:<6} {pnl_str:>10} ${float(trade.entry_price):>9.2f} ${float(trade.exit_price):>9.2f} {result}")
        self.stdout.write("")

    def analyze_signals(self):
        """Analyze signal generation"""
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("SIGNAL GENERATION ANALYSIS"))
        self.stdout.write("=" * 60)
        self.stdout.write("")

        # Get signal statistics
        total_signals = Signal.objects.count()
        bullish_signals = Signal.objects.filter(direction='LONG').count()
        bearish_signals = Signal.objects.filter(direction='SHORT').count()

        self.stdout.write("SIGNAL STATISTICS:")
        self.stdout.write(f"  Total Signals:     {total_signals}")
        if total_signals > 0:
            self.stdout.write(f"  Bullish (LONG):    {bullish_signals} ({bullish_signals/total_signals*100:.1f}%)")
            self.stdout.write(f"  Bearish (SHORT):   {bearish_signals} ({bearish_signals/total_signals*100:.1f}%)")
        else:
            self.stdout.write("  Bullish (LONG):    0")
            self.stdout.write("  Bearish (SHORT):   0")
        self.stdout.write("")

        # Signals by symbol
        self.stdout.write("TOP 10 SYMBOLS BY SIGNAL COUNT:")
        signal_stats = Signal.objects.values('symbol').annotate(
            count=Count('id'),
            long_count=Count('id', filter=Q(direction='LONG')),
            short_count=Count('id', filter=Q(direction='SHORT'))
        ).order_by('-count')[:10]

        for stat in signal_stats:
            self.stdout.write(f"  {stat['symbol']:10s}: {stat['count']:4d} signals ({stat['long_count']:3d} LONG, {stat['short_count']:3d} SHORT)")

        if signal_stats.count() == 0:
            self.stdout.write("  No signals generated yet")
        self.stdout.write("")

        # Recent signals
        recent_signals = Signal.objects.order_by('-timestamp')[:10]

        if recent_signals.exists():
            self.stdout.write("LAST 10 SIGNALS:")
            self.stdout.write(f"  {'Symbol':<10} {'Direction':<6} {'Entry':>10} {'SL':>10} {'TP':>10} {'Timestamp'}")
            self.stdout.write(f"  {'-'*10} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*20}")
            for sig in recent_signals:
                ts = sig.timestamp.strftime('%Y-%m-%d %H:%M')
                self.stdout.write(f"  {sig.symbol:<10} {sig.direction:<6} ${float(sig.entry_price):>9.2f} ${float(sig.stop_loss):>9.2f} ${float(sig.take_profit):>9.2f} {ts}")
        self.stdout.write("")

    def get_signal_engine_config(self):
        """Get current signal engine configuration"""
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("SIGNAL ENGINE CONFIGURATION"))
        self.stdout.write("=" * 60)
        self.stdout.write("")

        try:
            from scanner.strategies.signal_engine import SignalConfig
            config = SignalConfig()

            self.stdout.write("Current parameters from signal_engine.py:")
            self.stdout.write(f"  LONG RSI Range:    {config.long_rsi_min} - {config.long_rsi_max}")
            self.stdout.write(f"  SHORT RSI Range:   {config.short_rsi_min} - {config.short_rsi_max}")
            self.stdout.write(f"  ADX Min (LONG):    {config.long_adx_min}")
            self.stdout.write(f"  ADX Min (SHORT):   {config.short_adx_min}")
            self.stdout.write(f"  SL ATR Mult:       {config.sl_atr_multiplier}x")
            self.stdout.write(f"  TP ATR Mult:       {config.tp_atr_multiplier}x")
            self.stdout.write(f"  Min Confidence:    {config.min_confidence:.0%}")
            self.stdout.write(f"  Volume Multiplier: {config.long_volume_multiplier}x")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not load signal engine config: {e}"))
        self.stdout.write("")

    def provide_recommendations(self):
        """Provide improvement recommendations"""
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("RECOMMENDATIONS TO IMPROVE WIN RATE"))
        self.stdout.write("=" * 60)
        self.stdout.write("")

        # Get current performance
        closed_trades = PaperTrade.objects.filter(status='CLOSED').count()

        if closed_trades < 30:
            self.stdout.write(self.style.WARNING("INSUFFICIENT DATA WARNING:"))
            self.stdout.write(f"   You only have {closed_trades} closed trades.")
            self.stdout.write("   Recommendation: Collect at least 50-100 trades before optimization.")
            self.stdout.write("   Continue paper trading to gather more data.")
            self.stdout.write("")
            return

        winning_trades = PaperTrade.objects.filter(status='CLOSED', profit_loss__gt=0).count()
        win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0

        avg_win = float(PaperTrade.objects.filter(status='CLOSED', profit_loss__gt=0).aggregate(avg=Avg('profit_loss'))['avg'] or Decimal('0'))
        avg_loss = float(PaperTrade.objects.filter(status='CLOSED', profit_loss__lt=0).aggregate(avg=Avg('profit_loss'))['avg'] or Decimal('0'))

        self.stdout.write("Based on your current performance, here are recommendations:")
        self.stdout.write("")

        # Win rate analysis
        if win_rate < 40:
            self.stdout.write("1. LOW WIN RATE (<40%):")
            self.stdout.write("   Problem: Too many losing trades")
            self.stdout.write("   Solutions:")
            self.stdout.write("   • TIGHTEN signal filters - increase ADX threshold (25 → 30)")
            self.stdout.write("   • Add trend confirmation - only trade with trend")
            self.stdout.write("   • Increase RSI extreme levels (25/75 → 20/80)")
            self.stdout.write("   • Add volume filter - require volume spike confirmation")
            self.stdout.write("   • Consider using ML Tuning to optimize parameters")
            self.stdout.write("")
        elif win_rate < 50:
            self.stdout.write("1. MODERATE WIN RATE (40-50%):")
            self.stdout.write("   Your win rate is acceptable but can improve")
            self.stdout.write("   Solutions:")
            self.stdout.write("   • Fine-tune RSI levels for your symbols")
            self.stdout.write("   • Add momentum confirmation (MACD or similar)")
            self.stdout.write("   • Filter out low-probability signals")
            self.stdout.write("   • Use ML Tuning to find optimal parameters")
            self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("1. GOOD WIN RATE (>50%):"))
            self.stdout.write("   ✅ Your win rate is healthy!")
            self.stdout.write("   Focus on optimizing risk/reward ratio")
            self.stdout.write("")

        # Risk/Reward analysis
        if avg_loss != 0:
            risk_reward = abs(avg_win / avg_loss)

            if risk_reward < 1.5:
                self.stdout.write("2. LOW RISK/REWARD RATIO (<1.5):")
                self.stdout.write(f"   Current R:R = 1:{risk_reward:.2f}")
                self.stdout.write("   Problem: Wins are too small compared to losses")
                self.stdout.write("   Solutions:")
                self.stdout.write("   • INCREASE take profit target (TP ATR multiplier: 2.0 → 3.0)")
                self.stdout.write("   • DECREASE stop loss (SL ATR multiplier: 2.0 → 1.5)")
                self.stdout.write("   • Use trailing stop to capture larger moves")
                self.stdout.write("   • Let winners run longer")
                self.stdout.write("")
            elif risk_reward < 2.0:
                self.stdout.write("2. MODERATE RISK/REWARD RATIO (1.5-2.0):")
                self.stdout.write(f"   Current R:R = 1:{risk_reward:.2f}")
                self.stdout.write("   Acceptable but can improve")
                self.stdout.write("   • Consider increasing TP slightly")
                self.stdout.write("   • Test trailing stop strategies")
                self.stdout.write("")
            else:
                self.stdout.write(self.style.SUCCESS("2. GOOD RISK/REWARD RATIO (>2.0):"))
                self.stdout.write(f"   ✅ Current R:R = 1:{risk_reward:.2f}")
                self.stdout.write("   Your risk/reward is healthy!")
                self.stdout.write("")

        # Direction analysis
        long_trades = PaperTrade.objects.filter(status='CLOSED', direction='LONG')
        short_trades = PaperTrade.objects.filter(status='CLOSED', direction='SHORT')

        if long_trades.count() > 0 and short_trades.count() > 0:
            long_wins = long_trades.filter(profit_loss__gt=0).count()
            short_wins = short_trades.filter(profit_loss__gt=0).count()

            long_win_rate = (long_wins / long_trades.count() * 100)
            short_win_rate = (short_wins / short_trades.count() * 100)

            if abs(long_win_rate - short_win_rate) > 15:
                self.stdout.write("3. DIRECTIONAL BIAS:")
                better_dir = "LONG" if long_win_rate > short_win_rate else "SHORT"
                worse_dir = "SHORT" if long_win_rate > short_win_rate else "LONG"
                self.stdout.write(f"   {better_dir} trades perform significantly better ({long_win_rate:.1f}% vs {short_win_rate:.1f}%)")
                self.stdout.write("   Solutions:")
                self.stdout.write(f"   • Focus on {better_dir} signals")
                self.stdout.write(f"   • Avoid or tighten filters for {worse_dir} signals")
                self.stdout.write(f"   • Different parameters may work better for {worse_dir}")
                self.stdout.write("")

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("RECOMMENDED ACTION PLAN"))
        self.stdout.write("=" * 60)
        self.stdout.write("")
        self.stdout.write("STEP 1: Use ML-Based Tuning (Recommended)")
        self.stdout.write("  Run ML tuning to automatically find optimal parameters:")
        self.stdout.write("  $ docker-compose exec backend python manage.py run_mltuning")
        self.stdout.write("")
        self.stdout.write("  This will:")
        self.stdout.write("  • Test 100-500 parameter combinations automatically")
        self.stdout.write("  • Find parameters that maximize win rate and profit")
        self.stdout.write("  • Validate on out-of-sample data")
        self.stdout.write("  • Give you production-ready parameters")
        self.stdout.write("")
        self.stdout.write("STEP 2: Validate with Monte Carlo")
        self.stdout.write("  Test robustness of ML-tuned parameters:")
        self.stdout.write("  $ docker-compose exec backend python manage.py run_montecarlo")
        self.stdout.write("")
        self.stdout.write("STEP 3: Continue Paper Trading")
        self.stdout.write("  Let the optimized parameters run for 50-100 more trades")
        self.stdout.write("")
        self.stdout.write("STEP 4: Go Live")
        self.stdout.write("  Only when:")
        self.stdout.write("  • Win rate > 45%")
        self.stdout.write("  • Risk/Reward > 1.5")
        self.stdout.write("  • Profit Factor > 1.3")
        self.stdout.write("  • 100+ paper trades completed")
        self.stdout.write("")
