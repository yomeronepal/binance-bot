#!/usr/bin/env python
"""
Analyze Paper Trading Performance and Signals
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from signals.models import PaperTrade, Signal
from django.db.models import Avg, Count, Sum, Q, Max, Min
from decimal import Decimal
from datetime import datetime, timedelta

def analyze_paper_trades():
    """Analyze paper trading performance"""
    print("=" * 60)
    print("PAPER TRADING PERFORMANCE ANALYSIS")
    print("=" * 60)
    print()

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

    print("TRADE STATISTICS:")
    print(f"  Total Trades:      {total_trades}")
    print(f"  Closed Trades:     {closed_trades}")
    print(f"  Open Trades:       {open_trades}")
    print(f"  Winning Trades:    {winning_trades} ({winning_trades/closed_trades*100:.1f}%)" if closed_trades > 0 else "  Winning Trades:    0")
    print(f"  Losing Trades:     {losing_trades} ({losing_trades/closed_trades*100:.1f}%)" if closed_trades > 0 else "  Losing Trades:     0")
    print(f"  Breakeven Trades:  {breakeven_trades}")
    print()

    print("PERFORMANCE METRICS:")
    print(f"  Win Rate:          {win_rate:.2f}%")
    print(f"  Average Win:       ${float(avg_win):.2f}")
    print(f"  Average Loss:      ${float(avg_loss):.2f}")
    print(f"  Max Win:           ${float(max_win):.2f}")
    print(f"  Max Loss:          ${float(max_loss):.2f}")
    print(f"  Total PnL:         ${float(total_pnl):.2f}")

    if losing_trades > 0 and float(avg_loss) != 0:
        profit_factor = abs(float(avg_win) * winning_trades / (float(avg_loss) * losing_trades))
        print(f"  Profit Factor:     {profit_factor:.2f}")

        # Risk/Reward Ratio
        risk_reward = abs(float(avg_win) / float(avg_loss))
        print(f"  Risk/Reward Ratio: 1:{risk_reward:.2f}")

        # Expectancy
        expectancy = (win_rate/100 * float(avg_win)) - ((100-win_rate)/100 * abs(float(avg_loss)))
        print(f"  Expectancy:        ${expectancy:.2f} per trade")
    print()

    # Analyze by direction
    print("BY DIRECTION:")
    long_trades = PaperTrade.objects.filter(status='CLOSED', direction='LONG')
    short_trades = PaperTrade.objects.filter(status='CLOSED', direction='SHORT')

    long_count = long_trades.count()
    short_count = short_trades.count()

    if long_count > 0:
        long_wins = long_trades.filter(profit_loss__gt=0).count()
        long_win_rate = (long_wins / long_count * 100)
        long_pnl = long_trades.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
        print(f"  LONG Trades:  {long_count} trades, {long_win_rate:.1f}% win rate, ${float(long_pnl):.2f} PnL")
    else:
        print(f"  LONG Trades:  0 trades")

    if short_count > 0:
        short_wins = short_trades.filter(profit_loss__gt=0).count()
        short_win_rate = (short_wins / short_count * 100)
        short_pnl = short_trades.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
        print(f"  SHORT Trades: {short_count} trades, {short_win_rate:.1f}% win rate, ${float(short_pnl):.2f} PnL")
    else:
        print(f"  SHORT Trades: 0 trades")
    print()

    # Analyze by symbol
    print("TOP 5 SYMBOLS BY TRADE COUNT:")
    symbol_stats = PaperTrade.objects.filter(status='CLOSED').values('symbol').annotate(
        count=Count('id'),
        wins=Count('id', filter=Q(profit_loss__gt=0)),
        total_pnl=Sum('profit_loss')
    ).order_by('-count')[:5]

    for stat in symbol_stats:
        win_rate_sym = (stat['wins'] / stat['count'] * 100) if stat['count'] > 0 else 0
        print(f"  {stat['symbol']:10s}: {stat['count']:3d} trades, {win_rate_sym:5.1f}% win rate, ${float(stat['total_pnl'] or 0):8.2f} PnL")

    if symbol_stats.count() == 0:
        print("  No closed trades yet")
    print()

    # Recent performance
    recent_trades = PaperTrade.objects.filter(
        status='CLOSED'
    ).order_by('-exit_time')[:20]

    if recent_trades.exists():
        print("LAST 20 CLOSED TRADES:")
        print(f"  {'Symbol':<10} {'Direction':<6} {'PnL':>10} {'Entry':>10} {'Exit':>10} {'Status'}")
        print(f"  {'-'*10} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
        for trade in recent_trades:
            pnl_str = f"${float(trade.profit_loss):.2f}"
            result = "WIN" if trade.profit_loss > 0 else "LOSS" if trade.profit_loss < 0 else "BE"
            print(f"  {trade.symbol:<10} {trade.direction:<6} {pnl_str:>10} ${float(trade.entry_price):>9.2f} ${float(trade.exit_price):>9.2f} {result}")
    print()

def analyze_signals():
    """Analyze signal generation"""
    print("=" * 60)
    print("SIGNAL GENERATION ANALYSIS")
    print("=" * 60)
    print()

    # Get signal statistics
    total_signals = Signal.objects.count()
    bullish_signals = Signal.objects.filter(direction='LONG').count()
    bearish_signals = Signal.objects.filter(direction='SHORT').count()

    print("SIGNAL STATISTICS:")
    print(f"  Total Signals:     {total_signals}")
    print(f"  Bullish (LONG):    {bullish_signals} ({bullish_signals/total_signals*100:.1f}%)" if total_signals > 0 else "  Bullish (LONG):    0")
    print(f"  Bearish (SHORT):   {bearish_signals} ({bearish_signals/total_signals*100:.1f}%)" if total_signals > 0 else "  Bearish (SHORT):   0")
    print()

    # Signals by symbol
    print("TOP 10 SYMBOLS BY SIGNAL COUNT:")
    signal_stats = Signal.objects.values('symbol').annotate(
        count=Count('id'),
        long_count=Count('id', filter=Q(direction='LONG')),
        short_count=Count('id', filter=Q(direction='SHORT'))
    ).order_by('-count')[:10]

    for stat in signal_stats:
        print(f"  {stat['symbol']:10s}: {stat['count']:4d} signals ({stat['long_count']:3d} LONG, {stat['short_count']:3d} SHORT)")

    if signal_stats.count() == 0:
        print("  No signals generated yet")
    print()

    # Recent signals
    recent_signals = Signal.objects.order_by('-timestamp')[:10]

    if recent_signals.exists():
        print("LAST 10 SIGNALS:")
        print(f"  {'Symbol':<10} {'Direction':<6} {'Entry':>10} {'SL':>10} {'TP':>10} {'Timestamp'}")
        print(f"  {'-'*10} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*20}")
        for sig in recent_signals:
            ts = sig.timestamp.strftime('%Y-%m-%d %H:%M')
            print(f"  {sig.symbol:<10} {sig.direction:<6} ${float(sig.entry_price):>9.2f} ${float(sig.stop_loss):>9.2f} ${float(sig.take_profit):>9.2f} {ts}")
    print()

def get_signal_engine_config():
    """Get current signal engine configuration"""
    print("=" * 60)
    print("SIGNAL ENGINE CONFIGURATION")
    print("=" * 60)
    print()

    try:
        from scanner.strategies.signal_engine import SignalEngine
        engine = SignalEngine()

        print("Current parameters from signal_engine.py:")
        print(f"  RSI Period:        {getattr(engine, 'rsi_period', 'N/A')}")
        print(f"  RSI Oversold:      {getattr(engine, 'rsi_oversold', 'N/A')}")
        print(f"  RSI Overbought:    {getattr(engine, 'rsi_overbought', 'N/A')}")
        print(f"  ADX Period:        {getattr(engine, 'adx_period', 'N/A')}")
        print(f"  ADX Threshold:     {getattr(engine, 'adx_threshold', 'N/A')}")
        print(f"  Volume Multiplier: {getattr(engine, 'volume_multiplier', 'N/A')}")
        print(f"  ATR Period:        {getattr(engine, 'atr_period', 'N/A')}")
        print(f"  SL ATR Mult:       {getattr(engine, 'sl_atr_multiplier', 'N/A')}")
        print(f"  TP ATR Mult:       {getattr(engine, 'tp_atr_multiplier', 'N/A')}")
    except Exception as e:
        print(f"Could not load signal engine config: {e}")
    print()

def provide_recommendations():
    """Provide improvement recommendations"""
    print("=" * 60)
    print("RECOMMENDATIONS TO IMPROVE WIN RATE")
    print("=" * 60)
    print()

    # Get current performance
    closed_trades = PaperTrade.objects.filter(status='CLOSED').count()

    if closed_trades < 30:
        print("⚠️  INSUFFICIENT DATA WARNING:")
        print(f"   You only have {closed_trades} closed trades.")
        print("   Recommendation: Collect at least 50-100 trades before optimization.")
        print("   Continue paper trading to gather more data.")
        print()
        return

    winning_trades = PaperTrade.objects.filter(status='CLOSED', profit_loss__gt=0).count()
    win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0

    avg_win = float(PaperTrade.objects.filter(status='CLOSED', profit_loss__gt=0).aggregate(avg=Avg('profit_loss'))['avg'] or Decimal('0'))
    avg_loss = float(PaperTrade.objects.filter(status='CLOSED', profit_loss__lt=0).aggregate(avg=Avg('profit_loss'))['avg'] or Decimal('0'))

    print("Based on your current performance, here are recommendations:")
    print()

    # Win rate analysis
    if win_rate < 40:
        print("1. LOW WIN RATE (<40%):")
        print("   Problem: Too many losing trades")
        print("   Solutions:")
        print("   • TIGHTEN signal filters - increase ADX threshold (25 → 30)")
        print("   • Add trend confirmation - only trade with trend")
        print("   • Increase RSI extreme levels (25/75 → 20/80)")
        print("   • Add volume filter - require volume spike confirmation")
        print("   • Consider using ML Tuning to optimize parameters")
        print()
    elif win_rate < 50:
        print("1. MODERATE WIN RATE (40-50%):")
        print("   Your win rate is acceptable but can improve")
        print("   Solutions:")
        print("   • Fine-tune RSI levels for your symbols")
        print("   • Add momentum confirmation (MACD or similar)")
        print("   • Filter out low-probability signals")
        print("   • Use ML Tuning to find optimal parameters")
        print()
    else:
        print("1. GOOD WIN RATE (>50%):")
        print("   ✅ Your win rate is healthy!")
        print("   Focus on optimizing risk/reward ratio")
        print()

    # Risk/Reward analysis
    if avg_loss != 0:
        risk_reward = abs(avg_win / avg_loss)

        if risk_reward < 1.5:
            print("2. LOW RISK/REWARD RATIO (<1.5):")
            print(f"   Current R:R = 1:{risk_reward:.2f}")
            print("   Problem: Wins are too small compared to losses")
            print("   Solutions:")
            print("   • INCREASE take profit target (TP ATR multiplier: 2.0 → 3.0)")
            print("   • DECREASE stop loss (SL ATR multiplier: 2.0 → 1.5)")
            print("   • Use trailing stop to capture larger moves")
            print("   • Let winners run longer")
            print()
        elif risk_reward < 2.0:
            print("2. MODERATE RISK/REWARD RATIO (1.5-2.0):")
            print(f"   Current R:R = 1:{risk_reward:.2f}")
            print("   Acceptable but can improve")
            print("   • Consider increasing TP slightly")
            print("   • Test trailing stop strategies")
            print()
        else:
            print("2. GOOD RISK/REWARD RATIO (>2.0):")
            print(f"   ✅ Current R:R = 1:{risk_reward:.2f}")
            print("   Your risk/reward is healthy!")
            print()

    # Direction analysis
    long_trades = PaperTrade.objects.filter(status='CLOSED', direction='LONG')
    short_trades = PaperTrade.objects.filter(status='CLOSED', direction='SHORT')

    if long_trades.count() > 0 and short_trades.count() > 0:
        long_wins = long_trades.filter(profit_loss__gt=0).count()
        short_wins = short_trades.filter(profit_loss__gt=0).count()

        long_win_rate = (long_wins / long_trades.count() * 100)
        short_win_rate = (short_wins / short_trades.count() * 100)

        if abs(long_win_rate - short_win_rate) > 15:
            print("3. DIRECTIONAL BIAS:")
            better_dir = "LONG" if long_win_rate > short_win_rate else "SHORT"
            worse_dir = "SHORT" if long_win_rate > short_win_rate else "LONG"
            print(f"   {better_dir} trades perform significantly better ({long_win_rate:.1f}% vs {short_win_rate:.1f}%)")
            print("   Solutions:")
            print(f"   • Focus on {better_dir} signals")
            print(f"   • Avoid or tighten filters for {worse_dir} signals")
            print(f"   • Different parameters may work better for {worse_dir}")
            print()

    print()
    print("=" * 60)
    print("RECOMMENDED ACTION PLAN")
    print("=" * 60)
    print()
    print("STEP 1: Use ML-Based Tuning (Recommended)")
    print("  Run ML tuning to automatically find optimal parameters:")
    print("  $ ./test_mltuning.sh")
    print()
    print("  This will:")
    print("  • Test 100-500 parameter combinations automatically")
    print("  • Find parameters that maximize win rate and profit")
    print("  • Validate on out-of-sample data")
    print("  • Give you production-ready parameters")
    print()
    print("STEP 2: Validate with Monte Carlo")
    print("  Test robustness of ML-tuned parameters:")
    print("  $ ./test_montecarlo.sh")
    print()
    print("STEP 3: Continue Paper Trading")
    print("  Let the optimized parameters run for 50-100 more trades")
    print()
    print("STEP 4: Go Live")
    print("  Only when:")
    print("  • Win rate > 45%")
    print("  • Risk/Reward > 1.5")
    print("  • Profit Factor > 1.3")
    print("  • 100+ paper trades completed")
    print()

if __name__ == '__main__':
    analyze_paper_trades()
    analyze_signals()
    get_signal_engine_config()
    provide_recommendations()
