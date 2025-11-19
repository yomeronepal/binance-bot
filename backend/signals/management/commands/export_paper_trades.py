"""
Django management command to export paper trading data to JSON.

Usage:
    python manage.py export_paper_trades [options]
    docker exec docker-web-1 python manage.py export_paper_trades
    docker exec docker-web-1 python manage.py export_paper_trades --user 1
    docker exec docker-web-1 python manage.py export_paper_trades --output my_trades.json
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db.models import Avg, Sum, Count, Q

from signals.models import PaperTrade, PaperAccount, Signal

User = get_user_model()


class Command(BaseCommand):
    help = 'Export paper trading data to JSON for analysis and optimization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            type=str,
            help='Output JSON file path',
            default=None
        )
        parser.add_argument(
            '--user', '-u',
            type=int,
            help='Filter by user ID',
            default=None
        )
        parser.add_argument(
            '--days',
            type=int,
            help='Only export trades from last N days',
            default=None
        )

    def handle(self, *args, **options):
        output_file = options['output']
        user_id = options['user']
        days = options['days']

        self.stdout.write(self.style.SUCCESS('🚀 Starting paper trade export...'))
        self.stdout.write(f'📅 Export date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        if user_id:
            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(f'👤 Filtering for user: {user.username} (ID: {user_id})')
            except User.DoesNotExist:
                raise CommandError(f'User with ID {user_id} does not exist')
        else:
            self.stdout.write('👥 Exporting all users')

        if days:
            self.stdout.write(f'📆 Filtering last {days} days')

        self.stdout.write('')

        export_data = self.export_paper_trades(user_id, days)

        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'paper_trades_export_{timestamp}.json'

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=self.decimal_to_float)

        self.stdout.write(self.style.SUCCESS(f'\n✅ Export completed successfully!'))
        self.stdout.write(self.style.SUCCESS(f'📁 Output file: {output_file}'))

        summary = export_data['summary_statistics']
        self.stdout.write('\n📊 Summary Statistics:')
        self.stdout.write(f'   Total Trades: {summary["total_closed_trades"]}')
        self.stdout.write(f'   Win Rate: {summary["win_rate"]:.2f}%')
        self.stdout.write(f'   Total P/L: ${summary["total_profit_loss"]:.2f}')
        self.stdout.write(f'   Profit Factor: {summary["profit_factor"]:.2f}')
        self.stdout.write(f'   Sharpe Ratio: {summary["sharpe_ratio"]:.3f}')
        self.stdout.write(f'   Max Drawdown: {summary["max_drawdown_percentage"]:.2f}%')

        self.stdout.write('\n🔍 Analysis includes:')
        self.stdout.write(f'   ✓ By Symbol: {len(export_data["analysis_by_symbol"])} symbols')
        self.stdout.write(f'   ✓ By Direction: {len(export_data["analysis_by_direction"])} directions')
        self.stdout.write(f'   ✓ By Timeframe: {len(export_data["analysis_by_timeframe"])} timeframes')
        self.stdout.write(f'   ✓ By Exit Type: {len(export_data["analysis_by_exit_type"])} exit types')
        self.stdout.write(f'   ✓ Time Period Analysis: {len(export_data["performance_by_period"])} periods')
        self.stdout.write(f'   ✓ Account Data: {len(export_data["paper_accounts"])} accounts')

    def decimal_to_float(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def calculate_sharpe_ratio(self, trades, risk_free_rate=0.02):
        if not trades or len(trades) < 2:
            return 0

        returns = [t['profit_loss_percentage'] for t in trades if t.get('profit_loss_percentage')]

        if not returns:
            return 0

        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0

        sharpe = (avg_return - risk_free_rate) / std_dev
        return round(sharpe, 3)

    def calculate_max_drawdown(self, trades):
        if not trades:
            return 0

        cumulative_pnl = 0
        peak = 0
        max_dd = 0

        for trade in trades:
            cumulative_pnl += trade.get('profit_loss', 0)

            if cumulative_pnl > peak:
                peak = cumulative_pnl

            drawdown = peak - cumulative_pnl
            if drawdown > max_dd:
                max_dd = drawdown

        if peak == 0:
            return 0

        return round((max_dd / abs(peak)) * 100, 2)

    def analyze_consecutive_patterns(self, trades):
        if not trades:
            return {
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0,
                'avg_consecutive_wins': 0,
                'avg_consecutive_losses': 0
            }

        current_streak = 0
        current_type = None
        win_streaks = []
        loss_streaks = []

        for trade in trades:
            is_win = trade.get('profit_loss', 0) > 0

            if current_type is None:
                current_type = 'win' if is_win else 'loss'
                current_streak = 1
            elif (is_win and current_type == 'win') or (not is_win and current_type == 'loss'):
                current_streak += 1
            else:
                if current_type == 'win':
                    win_streaks.append(current_streak)
                else:
                    loss_streaks.append(current_streak)

                current_type = 'win' if is_win else 'loss'
                current_streak = 1

        if current_streak > 0:
            if current_type == 'win':
                win_streaks.append(current_streak)
            else:
                loss_streaks.append(current_streak)

        return {
            'max_consecutive_wins': max(win_streaks) if win_streaks else 0,
            'max_consecutive_losses': max(loss_streaks) if loss_streaks else 0,
            'avg_consecutive_wins': round(sum(win_streaks) / len(win_streaks), 2) if win_streaks else 0,
            'avg_consecutive_losses': round(sum(loss_streaks) / len(loss_streaks), 2) if loss_streaks else 0
        }

    def export_paper_trades(self, user_id=None, days=None):
        trades_query = PaperTrade.objects.select_related('signal', 'user').all()

        if user_id:
            trades_query = trades_query.filter(user_id=user_id)

        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            trades_query = trades_query.filter(created_at__gte=cutoff_date)

        all_trades = trades_query.order_by('-created_at')
        closed_trades = all_trades.filter(status__startswith='CLOSED')
        open_trades = all_trades.filter(status__in=['PENDING', 'OPEN'])

        self.stdout.write(f"📊 Found {all_trades.count()} total trades")
        self.stdout.write(f"   ✅ Closed: {closed_trades.count()}")
        self.stdout.write(f"   🔄 Open: {open_trades.count()}")

        closed_trades_list = []
        for trade in closed_trades:
            trade_data = {
                'id': trade.id,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'market_type': trade.market_type,
                'entry_price': self.decimal_to_float(trade.entry_price),
                'exit_price': self.decimal_to_float(trade.exit_price),
                'stop_loss': self.decimal_to_float(trade.stop_loss),
                'take_profit': self.decimal_to_float(trade.take_profit),
                'position_size': self.decimal_to_float(trade.position_size),
                'quantity': self.decimal_to_float(trade.quantity),
                'leverage': trade.leverage,
                'profit_loss': self.decimal_to_float(trade.profit_loss),
                'profit_loss_percentage': self.decimal_to_float(trade.profit_loss_percentage),
                'status': trade.status,
                'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
                'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
                'duration_hours': self.decimal_to_float(trade.duration_hours) if trade.duration_hours else None,
                'risk_reward_ratio': trade.risk_reward_ratio,
                'created_at': trade.created_at.isoformat(),
            }

            if trade.signal:
                trade_data['signal'] = {
                    'id': trade.signal.id,
                    'timeframe': trade.signal.timeframe,
                    'confidence': self.decimal_to_float(trade.signal.confidence),
                    'source': trade.signal.source,
                    'meta': trade.signal.meta,
                }

            if trade.user:
                trade_data['user_id'] = trade.user.id
                trade_data['username'] = trade.user.username

            closed_trades_list.append(trade_data)

        closed_trades_sorted = sorted(
            closed_trades_list,
            key=lambda x: x['exit_time'] if x['exit_time'] else x['created_at']
        )

        open_trades_list = []
        for trade in open_trades:
            trade_data = {
                'id': trade.id,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'market_type': trade.market_type,
                'entry_price': self.decimal_to_float(trade.entry_price),
                'stop_loss': self.decimal_to_float(trade.stop_loss),
                'take_profit': self.decimal_to_float(trade.take_profit),
                'position_size': self.decimal_to_float(trade.position_size),
                'quantity': self.decimal_to_float(trade.quantity),
                'leverage': trade.leverage,
                'status': trade.status,
                'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
                'risk_reward_ratio': trade.risk_reward_ratio,
                'created_at': trade.created_at.isoformat(),
            }

            if trade.signal:
                trade_data['signal'] = {
                    'id': trade.signal.id,
                    'timeframe': trade.signal.timeframe,
                    'confidence': self.decimal_to_float(trade.signal.confidence),
                    'source': trade.signal.source,
                }

            if trade.user:
                trade_data['user_id'] = trade.user.id
                trade_data['username'] = trade.user.username

            open_trades_list.append(trade_data)

        total_closed = len(closed_trades_sorted)
        winning_trades = [t for t in closed_trades_sorted if t['profit_loss'] > 0]
        losing_trades = [t for t in closed_trades_sorted if t['profit_loss'] < 0]
        breakeven_trades = [t for t in closed_trades_sorted if t['profit_loss'] == 0]

        total_profit = sum(t['profit_loss'] for t in closed_trades_sorted)
        total_profit_pct = sum(t['profit_loss_percentage'] for t in closed_trades_sorted)

        win_rate = (len(winning_trades) / total_closed * 100) if total_closed > 0 else 0

        avg_win = sum(t['profit_loss'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['profit_loss'] for t in losing_trades) / len(losing_trades) if losing_trades else 0

        profit_factor = (
            abs(sum(t['profit_loss'] for t in winning_trades)) /
            abs(sum(t['profit_loss'] for t in losing_trades))
            if losing_trades and sum(t['profit_loss'] for t in losing_trades) != 0
            else 0
        )

        sharpe_ratio = self.calculate_sharpe_ratio(closed_trades_sorted)
        max_drawdown = self.calculate_max_drawdown(closed_trades_sorted)
        consecutive_stats = self.analyze_consecutive_patterns(closed_trades_sorted)

        avg_duration = (
            sum(t['duration_hours'] for t in closed_trades_sorted if t['duration_hours']) /
            len([t for t in closed_trades_sorted if t['duration_hours']])
            if any(t['duration_hours'] for t in closed_trades_sorted)
            else 0
        )

        by_symbol = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'win_rate': 0,
            'avg_duration': 0
        })

        for trade in closed_trades_sorted:
            symbol = trade['symbol']
            by_symbol[symbol]['total_trades'] += 1
            by_symbol[symbol]['total_pnl'] += trade['profit_loss']

            if trade['profit_loss'] > 0:
                by_symbol[symbol]['winning_trades'] += 1
            elif trade['profit_loss'] < 0:
                by_symbol[symbol]['losing_trades'] += 1

            if trade['duration_hours']:
                by_symbol[symbol]['avg_duration'] += trade['duration_hours']

        for symbol, stats in by_symbol.items():
            if stats['total_trades'] > 0:
                stats['win_rate'] = round((stats['winning_trades'] / stats['total_trades']) * 100, 2)
                if stats['total_trades'] > 0:
                    stats['avg_duration'] = round(stats['avg_duration'] / stats['total_trades'], 2)
            stats['total_pnl'] = round(stats['total_pnl'], 2)

        by_direction = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0,
            'win_rate': 0
        })

        for trade in closed_trades_sorted:
            direction = trade['direction']
            by_direction[direction]['total_trades'] += 1
            by_direction[direction]['total_pnl'] += trade['profit_loss']

            if trade['profit_loss'] > 0:
                by_direction[direction]['winning_trades'] += 1

        for direction, stats in by_direction.items():
            if stats['total_trades'] > 0:
                stats['win_rate'] = round((stats['winning_trades'] / stats['total_trades']) * 100, 2)
            stats['total_pnl'] = round(stats['total_pnl'], 2)

        by_timeframe = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0,
            'win_rate': 0
        })

        for trade in closed_trades_sorted:
            if trade.get('signal'):
                timeframe = trade['signal']['timeframe']
                by_timeframe[timeframe]['total_trades'] += 1
                by_timeframe[timeframe]['total_pnl'] += trade['profit_loss']

                if trade['profit_loss'] > 0:
                    by_timeframe[timeframe]['winning_trades'] += 1

        for timeframe, stats in by_timeframe.items():
            if stats['total_trades'] > 0:
                stats['win_rate'] = round((stats['winning_trades'] / stats['total_trades']) * 100, 2)
            stats['total_pnl'] = round(stats['total_pnl'], 2)

        by_exit_type = defaultdict(lambda: {
            'count': 0,
            'total_pnl': 0,
            'avg_pnl': 0
        })

        for trade in closed_trades_sorted:
            exit_type = trade['status'].replace('CLOSED_', '')
            by_exit_type[exit_type]['count'] += 1
            by_exit_type[exit_type]['total_pnl'] += trade['profit_loss']

        for exit_type, stats in by_exit_type.items():
            if stats['count'] > 0:
                stats['avg_pnl'] = round(stats['total_pnl'] / stats['count'], 2)
            stats['total_pnl'] = round(stats['total_pnl'], 2)

        accounts_data = []
        if user_id:
            accounts = PaperAccount.objects.filter(user_id=user_id)
        else:
            accounts = PaperAccount.objects.all()

        for account in accounts:
            account_data = {
                'user_id': account.user.id,
                'username': account.user.username,
                'initial_balance': self.decimal_to_float(account.initial_balance),
                'current_balance': self.decimal_to_float(account.balance),
                'equity': self.decimal_to_float(account.equity),
                'total_pnl': self.decimal_to_float(account.total_pnl),
                'realized_pnl': self.decimal_to_float(account.realized_pnl),
                'unrealized_pnl': self.decimal_to_float(account.unrealized_pnl),
                'total_trades': account.total_trades,
                'winning_trades': account.winning_trades,
                'losing_trades': account.losing_trades,
                'win_rate': self.decimal_to_float(account.win_rate),
                'roi_percentage': round(
                    (self.decimal_to_float(account.total_pnl) / self.decimal_to_float(account.initial_balance)) * 100, 2
                ) if account.initial_balance > 0 else 0,
                'auto_trading_enabled': account.auto_trading_enabled,
                'max_position_size': self.decimal_to_float(account.max_position_size),
                'max_open_trades': account.max_open_trades,
                'min_signal_confidence': self.decimal_to_float(account.min_signal_confidence),
                'open_positions_count': len(account.open_positions),
                'created_at': account.created_at.isoformat(),
                'last_trade_at': account.last_trade_at.isoformat() if account.last_trade_at else None,
            }
            accounts_data.append(account_data)

        time_periods = {
            'last_7_days': [],
            'last_30_days': [],
            'last_90_days': [],
            'all_time': closed_trades_sorted
        }

        now = datetime.now()
        for trade in closed_trades_sorted:
            if trade['exit_time']:
                exit_dt = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))

                if (now - exit_dt).days <= 7:
                    time_periods['last_7_days'].append(trade)
                if (now - exit_dt).days <= 30:
                    time_periods['last_30_days'].append(trade)
                if (now - exit_dt).days <= 90:
                    time_periods['last_90_days'].append(trade)

        performance_by_period = {}
        for period_name, trades in time_periods.items():
            if trades:
                wins = [t for t in trades if t['profit_loss'] > 0]
                losses = [t for t in trades if t['profit_loss'] < 0]

                performance_by_period[period_name] = {
                    'total_trades': len(trades),
                    'winning_trades': len(wins),
                    'losing_trades': len(losses),
                    'win_rate': round((len(wins) / len(trades)) * 100, 2),
                    'total_pnl': round(sum(t['profit_loss'] for t in trades), 2),
                    'avg_pnl': round(sum(t['profit_loss'] for t in trades) / len(trades), 2),
                    'profit_factor': round(
                        abs(sum(t['profit_loss'] for t in wins)) /
                        abs(sum(t['profit_loss'] for t in losses)), 2
                    ) if losses and sum(t['profit_loss'] for t in losses) != 0 else 0,
                    'sharpe_ratio': self.calculate_sharpe_ratio(trades),
                    'max_drawdown': self.calculate_max_drawdown(trades)
                }
            else:
                performance_by_period[period_name] = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'avg_pnl': 0,
                    'profit_factor': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown': 0
                }

        export_data = {
            'export_info': {
                'generated_at': datetime.now().isoformat(),
                'user_filter': user_id,
                'total_trades_exported': len(closed_trades_sorted),
                'open_trades_exported': len(open_trades_list)
            },
            'summary_statistics': {
                'total_closed_trades': total_closed,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'breakeven_trades': len(breakeven_trades),
                'win_rate': round(win_rate, 2),
                'total_profit_loss': round(total_profit, 2),
                'total_profit_loss_percentage': round(total_profit_pct, 2),
                'average_win': round(avg_win, 2),
                'average_loss': round(avg_loss, 2),
                'profit_factor': round(profit_factor, 2),
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown_percentage': max_drawdown,
                'average_duration_hours': round(avg_duration, 2),
                **consecutive_stats
            },
            'closed_trades': closed_trades_sorted,
            'open_trades': open_trades_list,
            'analysis_by_symbol': dict(by_symbol),
            'analysis_by_direction': dict(by_direction),
            'analysis_by_timeframe': dict(by_timeframe),
            'analysis_by_exit_type': dict(by_exit_type),
            'performance_by_period': performance_by_period,
            'paper_accounts': accounts_data
        }

        return export_data
