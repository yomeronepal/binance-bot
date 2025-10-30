"""
Strategy Performance Service
Utility functions for aggregating backtest performance data
"""
from django.db.models import Avg, Sum, Count, Q
from collections import defaultdict
import logging

from signals.models_backtest import BacktestRun, BacktestTrade

logger = logging.getLogger(__name__)


def aggregate_by_volatility(backtests):
    """Aggregate performance metrics by volatility level"""
    volatility_stats = defaultdict(lambda: {
        'totalTrades': 0,
        'wins': 0,
        'losses': 0,
        'totalPnL': 0.0
    })

    for backtest in backtests:
        # Determine volatility level from symbols
        vol_level = determine_volatility_level(backtest.symbols)

        volatility_stats[vol_level]['totalTrades'] += backtest.total_trades or 0
        volatility_stats[vol_level]['wins'] += backtest.winning_trades or 0
        volatility_stats[vol_level]['losses'] += backtest.losing_trades or 0
        volatility_stats[vol_level]['totalPnL'] += float(backtest.total_profit_loss or 0)

    result = []
    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        if vol_level in volatility_stats:
            stats = volatility_stats[vol_level]
            win_rate = (stats['wins'] / stats['totalTrades'] * 100) if stats['totalTrades'] > 0 else 0
            result.append({
                'volatility': vol_level,
                'winRate': round(win_rate, 2),
                'totalTrades': stats['totalTrades'],
                'wins': stats['wins'],
                'losses': stats['losses'],
                'totalPnL': round(stats['totalPnL'], 2)
            })

    return result


def aggregate_by_symbol(backtests):
    """Aggregate performance metrics by trading symbol"""
    symbol_stats = defaultdict(lambda: {
        'trades': 0,
        'wins': 0,
        'losses': 0,
        'pnl': 0.0,
        'initialCapital': 0.0,
        'finalCapital': 0.0,
        'sharpeRatio': []
    })

    for backtest in backtests:
        for symbol in backtest.symbols:
            # Get trades for this symbol
            trades = BacktestTrade.objects.filter(
                backtest_run=backtest,
                symbol=symbol
            )

            wins = trades.filter(profit_loss__gt=0).count()
            losses = trades.filter(profit_loss__lte=0).count()
            total_pnl = sum(float(t.profit_loss or 0) for t in trades)

            symbol_stats[symbol]['trades'] += trades.count()
            symbol_stats[symbol]['wins'] += wins
            symbol_stats[symbol]['losses'] += losses
            symbol_stats[symbol]['pnl'] += total_pnl
            symbol_stats[symbol]['initialCapital'] = float(backtest.initial_capital)
            # Calculate final capital from initial + profit/loss
            final_cap = float(backtest.initial_capital) + float(backtest.total_profit_loss or 0)
            symbol_stats[symbol]['finalCapital'] = final_cap

            if backtest.sharpe_ratio:
                symbol_stats[symbol]['sharpeRatio'].append(float(backtest.sharpe_ratio))

    result = []
    for symbol, stats in symbol_stats.items():
        win_rate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        pnl_percent = (stats['pnl'] / stats['initialCapital'] * 100) if stats['initialCapital'] > 0 else 0
        avg_sharpe = sum(stats['sharpeRatio']) / len(stats['sharpeRatio']) if stats['sharpeRatio'] else 0

        result.append({
            'symbol': symbol,
            'trades': stats['trades'],
            'winRate': round(win_rate, 2),
            'pnl': round(stats['pnl'], 2),
            'pnlPercent': round(pnl_percent, 2),
            'sharpeRatio': round(avg_sharpe, 2) if avg_sharpe else None
        })

    return sorted(result, key=lambda x: x['pnlPercent'], reverse=True)


def aggregate_by_configuration(backtests):
    """Aggregate performance by strategy configuration"""
    config_stats = defaultdict(lambda: {
        'volatility': '',
        'symbols': set(),
        'totalTrades': 0,
        'wins': 0,
        'losses': 0,
        'totalPnL': 0.0,
        'sharpeRatios': [],
        'maxDrawdowns': [],
        'slMultiplier': 0,
        'tpMultiplier': 0,
        'adxThreshold': 0
    })

    for backtest in backtests:
        # Create config key based on strategy parameters
        params = backtest.strategy_params or {}
        config_key = f"{params.get('sl_atr_multiplier', 1.5)}x_{params.get('tp_atr_multiplier', 2.5)}x_{params.get('long_adx_min', 22)}"

        vol_level = determine_volatility_level(backtest.symbols)

        config_stats[config_key]['name'] = f"{vol_level} Vol Config"
        config_stats[config_key]['volatility'] = vol_level
        config_stats[config_key]['symbols'].update(backtest.symbols)
        config_stats[config_key]['totalTrades'] += backtest.total_trades or 0
        config_stats[config_key]['wins'] += backtest.winning_trades or 0
        config_stats[config_key]['losses'] += backtest.losing_trades or 0
        config_stats[config_key]['totalPnL'] += float(backtest.total_profit_loss or 0)
        config_stats[config_key]['slMultiplier'] = float(params.get('sl_atr_multiplier', 1.5))
        config_stats[config_key]['tpMultiplier'] = float(params.get('tp_atr_multiplier', 2.5))
        config_stats[config_key]['adxThreshold'] = float(params.get('long_adx_min', 22))

        if backtest.sharpe_ratio:
            config_stats[config_key]['sharpeRatios'].append(float(backtest.sharpe_ratio))
        if backtest.max_drawdown:
            config_stats[config_key]['maxDrawdowns'].append(float(backtest.max_drawdown))

    result = []
    for config_key, stats in config_stats.items():
        win_rate = (stats['wins'] / stats['totalTrades'] * 100) if stats['totalTrades'] > 0 else 0
        avg_sharpe = sum(stats['sharpeRatios']) / len(stats['sharpeRatios']) if stats['sharpeRatios'] else 0
        max_dd = max(stats['maxDrawdowns']) if stats['maxDrawdowns'] else 0
        avg_return = (stats['totalPnL'] / (stats['totalTrades'] or 1)) if stats['totalTrades'] > 0 else 0

        result.append({
            'name': stats['name'],
            'volatility': stats['volatility'],
            'symbols': list(stats['symbols']),
            'totalTrades': stats['totalTrades'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'winRate': round(win_rate, 2),
            'totalPnL': round(stats['totalPnL'], 2),
            'avgReturn': round(avg_return, 2),
            'sharpeRatio': round(avg_sharpe, 2) if avg_sharpe else None,
            'maxDrawdown': round(max_dd, 2),
            'slMultiplier': stats['slMultiplier'],
            'tpMultiplier': stats['tpMultiplier'],
            'adxThreshold': stats['adxThreshold']
        })

    return sorted(result, key=lambda x: x['totalPnL'], reverse=True)


def calculate_sharpe_over_time(backtests):
    """Calculate Sharpe ratio trend over time"""
    # Group backtests by date
    sharpe_by_date = defaultdict(list)

    for backtest in backtests:
        if backtest.sharpe_ratio:
            date_str = backtest.created_at.strftime('%Y-%m-%d')
            sharpe_by_date[date_str].append({
                'sharpe': float(backtest.sharpe_ratio),
                'return': float(backtest.roi or 0),
                'volatility': float(backtest.max_drawdown or 0)
            })

    result = []
    for date_str in sorted(sharpe_by_date.keys()):
        stats = sharpe_by_date[date_str]
        avg_sharpe = sum(s['sharpe'] for s in stats) / len(stats)
        avg_return = sum(s['return'] for s in stats) / len(stats)
        avg_volatility = sum(s['volatility'] for s in stats) / len(stats)

        result.append({
            'date': date_str,
            'sharpeRatio': round(avg_sharpe, 2),
            'return': round(avg_return, 2),
            'volatility': round(avg_volatility, 2)
        })

    return result


def generate_performance_heatmap(backtests):
    """Generate performance heatmap data"""
    # Group by symbol and time period
    heatmap_data = defaultdict(lambda: defaultdict(lambda: {
        'value': 0,
        'trades': 0,
        'wins': 0,
        'losses': 0
    }))

    for backtest in backtests:
        period = backtest.created_at.strftime('%b')  # Month abbreviation

        for symbol in backtest.symbols:
            trades = BacktestTrade.objects.filter(
                backtest_run=backtest,
                symbol=symbol
            )

            wins = trades.filter(profit_loss__gt=0).count()
            losses = trades.filter(profit_loss__lte=0).count()
            total_pnl = sum(float(t.profit_loss or 0) for t in trades)

            # Calculate return percentage (assuming $1000 initial capital)
            return_pct = (total_pnl / 1000 * 100) if trades.count() > 0 else 0

            heatmap_data[symbol][period]['value'] = return_pct
            heatmap_data[symbol][period]['trades'] = trades.count()
            heatmap_data[symbol][period]['wins'] = wins
            heatmap_data[symbol][period]['losses'] = losses

    # Convert to list format
    result = []
    periods = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    for symbol in sorted(heatmap_data.keys()):
        periods_data = []
        for period in periods:
            data = heatmap_data[symbol].get(period, {'value': None, 'trades': 0, 'wins': 0, 'losses': 0})
            win_rate = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0

            periods_data.append({
                'name': period,
                'value': round(data['value'], 1) if data['value'] is not None else None,
                'trades': data['trades'],
                'winRate': round(win_rate, 1) if data['trades'] > 0 else 0
            })

        result.append({
            'symbol': symbol,
            'periods': periods_data
        })

    return result


def get_ml_optimization_results():
    """Get ML optimization results if available"""
    # This would integrate with the ML tuning module
    # For now, return None
    return None


def determine_volatility_level(symbols):
    """Determine volatility level from symbols"""
    high_vol_symbols = {'DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT', 'WIFUSDT'}
    low_vol_symbols = {'BTCUSDT', 'ETHUSDT', 'BNBUSDT'}

    for symbol in symbols:
        if symbol in high_vol_symbols:
            return 'HIGH'
        elif symbol in low_vol_symbols:
            return 'LOW'

    return 'MEDIUM'
