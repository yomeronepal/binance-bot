"""
Signal admin configuration following DRY principles.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Symbol, Signal, UserSubscription, PaperTrade, PaperAccount
from .models_backtest import (
    BacktestRun,
    BacktestTrade,
    StrategyOptimization,
    OptimizationRecommendation,
    BacktestMetric
)
from .models_walkforward import (
    WalkForwardOptimization,
    WalkForwardWindow,
    WalkForwardMetric
)
from .models_montecarlo import (
    MonteCarloSimulation,
    MonteCarloRun,
    MonteCarloDistribution
)
from .models_mltuning import (
    MLTuningJob,
    MLTuningSample,
    MLPrediction,
    MLModel
)


class BaseModelAdmin(admin.ModelAdmin):
    """
    Base admin class with common configurations (DRY principle).
    """
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    show_full_result_count = True


@admin.register(Symbol)
class SymbolAdmin(BaseModelAdmin):
    """
    Admin interface for Symbol model.
    """
    list_display = ('symbol', 'exchange', 'active', 'active_signals_count', 'created_at')
    list_filter = ('active', 'exchange', 'created_at')
    search_fields = ('symbol', 'exchange')
    ordering = ('symbol',)
    list_per_page = 50

    actions = ['activate_symbols', 'deactivate_symbols']

    def active_signals_count(self, obj):
        """Display count of active signals for this symbol."""
        count = obj.signals.filter(status='ACTIVE').count()
        if count > 0:
            return format_html('<strong>{}</strong>', count)
        return count
    active_signals_count.short_description = 'Active Signals'

    @admin.action(description='Activate selected symbols')
    def activate_symbols(self, request, queryset):
        """Bulk activate symbols."""
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} symbols activated successfully.')

    @admin.action(description='Deactivate selected symbols')
    def deactivate_symbols(self, request, queryset):
        """Bulk deactivate symbols."""
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} symbols deactivated successfully.')


@admin.register(Signal)
class SignalAdmin(BaseModelAdmin):
    """
    Admin interface for Signal model.
    """
    list_display = (
        'id',
        'symbol_display',
        'direction',
        'timeframe',
        'entry',
        'sl',
        'tp',
        'confidence_display',
        'rr_ratio',
        'status_badge',
        'created_at'
    )
    list_filter = (
        'direction',
        'status',
        'timeframe',
        'symbol__exchange',
        'created_at',
        'confidence'
    )
    search_fields = (
        'symbol__symbol',
        'description',
        'source',
        'created_by__username'
    )
    ordering = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Information', {
            'fields': ('symbol', 'direction', 'timeframe', 'status')
        }),
        ('Price Levels', {
            'fields': ('entry', 'sl', 'tp')
        }),
        ('Signal Details', {
            'fields': ('confidence', 'source', 'description', 'meta')
        }),
        ('Metadata', {
            'fields': ('created_by', 'expires_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    autocomplete_fields = ['symbol', 'created_by']
    actions = ['mark_as_executed', 'mark_as_expired', 'mark_as_cancelled']

    def symbol_display(self, obj):
        """Display symbol with exchange."""
        return f"{obj.symbol.symbol} ({obj.symbol.exchange})"
    symbol_display.short_description = 'Symbol'
    symbol_display.admin_order_field = 'symbol__symbol'

    def confidence_display(self, obj):
        """Display confidence as percentage with color."""
        percentage = int(obj.confidence * 100)
        if obj.confidence >= 0.8:
            color = 'green'
        elif obj.confidence >= 0.5:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            percentage
        )
    confidence_display.short_description = 'Confidence'
    confidence_display.admin_order_field = 'confidence'

    def rr_ratio(self, obj):
        """Display risk/reward ratio."""
        ratio = obj.risk_reward_ratio
        if ratio:
            if ratio >= 2:
                color = 'green'
            elif ratio >= 1:
                color = 'orange'
            else:
                color = 'red'
            return format_html(
                '<span style="color: {};">1:{}</span>',
                color,
                ratio
            )
        return '—'
    rr_ratio.short_description = 'R:R'

    def status_badge(self, obj):
        """Display status with colored badge."""
        colors = {
            'ACTIVE': '#28a745',
            'EXECUTED': '#007bff',
            'EXPIRED': '#6c757d',
            'CANCELLED': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    @admin.action(description='Mark selected signals as EXECUTED')
    def mark_as_executed(self, request, queryset):
        """Bulk mark signals as executed."""
        updated = queryset.update(status='EXECUTED')
        self.message_user(request, f'{updated} signals marked as EXECUTED.')

    @admin.action(description='Mark selected signals as EXPIRED')
    def mark_as_expired(self, request, queryset):
        """Bulk mark signals as expired."""
        updated = queryset.update(status='EXPIRED')
        self.message_user(request, f'{updated} signals marked as EXPIRED.')

    @admin.action(description='Mark selected signals as CANCELLED')
    def mark_as_cancelled(self, request, queryset):
        """Bulk mark signals as cancelled."""
        updated = queryset.update(status='CANCELLED')
        self.message_user(request, f'{updated} signals marked as CANCELLED.')

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related('symbol', 'created_by')


@admin.register(UserSubscription)
class UserSubscriptionAdmin(BaseModelAdmin):
    """
    Admin interface for UserSubscription model.
    """
    list_display = (
        'user_display',
        'tier_badge',
        'status_badge',
        'is_premium',
        'is_active',
        'expires_at',
        'created_at'
    )
    list_filter = (
        'tier',
        'status',
        'created_at',
        'expires_at'
    )
    search_fields = (
        'user__username',
        'user__email',
        'stripe_customer_id',
        'stripe_subscription_id'
    )
    ordering = ('-created_at',)
    list_per_page = 50

    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Subscription Details', {
            'fields': ('tier', 'status', 'expires_at')
        }),
        ('Stripe Information', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    autocomplete_fields = ['user']
    actions = ['upgrade_to_pro', 'upgrade_to_premium', 'downgrade_to_free', 'cancel_subscriptions']

    def user_display(self, obj):
        """Display user with email."""
        return f"{obj.user.username} ({obj.user.email})"
    user_display.short_description = 'User'
    user_display.admin_order_field = 'user__username'

    def tier_badge(self, obj):
        """Display tier with colored badge."""
        colors = {
            'free': '#6c757d',
            'pro': '#007bff',
            'premium': '#ffc107'
        }
        color = colors.get(obj.tier, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; text-transform: uppercase;">{}</span>',
            color,
            obj.tier
        )
    tier_badge.short_description = 'Tier'
    tier_badge.admin_order_field = 'tier'

    def status_badge(self, obj):
        """Display status with colored badge."""
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'cancelled': '#dc3545',
            'expired': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    @admin.action(description='Upgrade to PRO')
    def upgrade_to_pro(self, request, queryset):
        """Bulk upgrade to PRO tier."""
        updated = queryset.update(tier='pro', status='active')
        self.message_user(request, f'{updated} subscriptions upgraded to PRO.')

    @admin.action(description='Upgrade to PREMIUM')
    def upgrade_to_premium(self, request, queryset):
        """Bulk upgrade to PREMIUM tier."""
        updated = queryset.update(tier='premium', status='active')
        self.message_user(request, f'{updated} subscriptions upgraded to PREMIUM.')

    @admin.action(description='Downgrade to FREE')
    def downgrade_to_free(self, request, queryset):
        """Bulk downgrade to FREE tier."""
        updated = queryset.update(tier='free', status='active')
        self.message_user(request, f'{updated} subscriptions downgraded to FREE.')

    @admin.action(description='Cancel subscriptions')
    def cancel_subscriptions(self, request, queryset):
        """Bulk cancel subscriptions."""
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} subscriptions cancelled.')

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related('user')


@admin.register(PaperTrade)
class PaperTradeAdmin(BaseModelAdmin):
    """
    Admin interface for PaperTrade model.
    """
    list_display = (
        'id',
        'symbol',
        'direction',
        'market_type',
        'entry_price',
        'exit_price',
        'status_badge',
        'profit_loss_display',
        'profit_loss_percentage',
        'user_display',
        'created_at'
    )
    list_filter = (
        'status',
        'direction',
        'market_type',
        'created_at',
        'exit_time'
    )
    search_fields = (
        'symbol',
        'user__username',
        'signal__id'
    )
    ordering = ('-created_at',)
    list_per_page = 50

    fieldsets = (
        ('Trade Information', {
            'fields': ('user', 'signal', 'symbol', 'direction', 'market_type', 'status')
        }),
        ('Entry Details', {
            'fields': ('entry_price', 'entry_time', 'position_size', 'quantity', 'leverage')
        }),
        ('Exit Details', {
            'fields': ('stop_loss', 'take_profit', 'exit_price', 'exit_time')
        }),
        ('Performance', {
            'fields': ('profit_loss', 'profit_loss_percentage')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ('profit_loss', 'profit_loss_percentage', 'exit_time', 'quantity')
    autocomplete_fields = ['user', 'signal']

    def user_display(self, obj):
        """Display user."""
        return obj.user.username if obj.user else 'System'
    user_display.short_description = 'User'
    user_display.admin_order_field = 'user__username'

    def profit_loss_display(self, obj):
        """Display profit/loss with color."""
        pnl = float(obj.profit_loss)
        if pnl > 0:
            color = 'green'
            sign = '+'
        elif pnl < 0:
            color = 'red'
            sign = ''
        else:
            color = 'gray'
            sign = ''
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{:.2f} USDT</span>',
            color,
            sign,
            pnl
        )
    profit_loss_display.short_description = 'P/L'
    profit_loss_display.admin_order_field = 'profit_loss'

    def status_badge(self, obj):
        """Display status with colored badge."""
        colors = {
            'OPEN': '#007bff',
            'CLOSED_TP': '#28a745',
            'CLOSED_SL': '#dc3545',
            'CLOSED_MANUAL': '#6c757d',
            'PENDING': '#ffc107',
            'CANCELLED': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.status.replace('_', ' ')
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related('user', 'signal')


@admin.register(PaperAccount)
class PaperAccountAdmin(BaseModelAdmin):
    """
    Admin interface for PaperAccount model (Auto-Trading).
    """
    list_display = (
        'user_display',
        'balance_display',
        'equity_display',
        'total_pnl_display',
        'win_rate_display',
        'total_trades',
        'open_positions_count',
        'auto_trading_status',
        'created_at'
    )
    list_filter = (
        'auto_trading_enabled',
        'auto_trade_spot',
        'auto_trade_futures',
        'created_at'
    )
    search_fields = (
        'user__username',
        'user__email'
    )
    ordering = ('-created_at',)
    list_per_page = 50

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Balance & Equity', {
            'fields': ('initial_balance', 'balance', 'equity')
        }),
        ('Performance Metrics', {
            'fields': (
                'total_pnl',
                'realized_pnl',
                'unrealized_pnl',
                'total_trades',
                'winning_trades',
                'losing_trades',
                'win_rate'
            )
        }),
        ('Risk Management', {
            'fields': ('max_position_size', 'max_open_trades')
        }),
        ('Auto-Trading Settings', {
            'fields': (
                'auto_trading_enabled',
                'auto_trade_spot',
                'auto_trade_futures',
                'min_signal_confidence'
            )
        }),
        ('Open Positions', {
            'fields': ('open_positions',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('last_trade_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    readonly_fields = (
        'balance',
        'equity',
        'total_pnl',
        'realized_pnl',
        'unrealized_pnl',
        'total_trades',
        'winning_trades',
        'losing_trades',
        'win_rate',
        'open_positions',
        'last_trade_at'
    )
    autocomplete_fields = ['user']
    actions = ['reset_accounts', 'enable_auto_trading', 'disable_auto_trading']

    def user_display(self, obj):
        """Display user."""
        return f"{obj.user.username} ({obj.user.email})"
    user_display.short_description = 'User'
    user_display.admin_order_field = 'user__username'

    def balance_display(self, obj):
        """Display balance."""
        return format_html(
            '<span style="font-weight: bold;">${:,.2f}</span>',
            float(obj.balance)
        )
    balance_display.short_description = 'Balance'
    balance_display.admin_order_field = 'balance'

    def equity_display(self, obj):
        """Display equity."""
        return format_html(
            '<span style="font-weight: bold;">${:,.2f}</span>',
            float(obj.equity)
        )
    equity_display.short_description = 'Equity'
    equity_display.admin_order_field = 'equity'

    def total_pnl_display(self, obj):
        """Display total P/L with color."""
        pnl = float(obj.total_pnl)
        if pnl > 0:
            color = 'green'
            sign = '+'
        elif pnl < 0:
            color = 'red'
            sign = ''
        else:
            color = 'gray'
            sign = ''
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{:.2f}</span>',
            color,
            sign,
            pnl
        )
    total_pnl_display.short_description = 'Total P/L'
    total_pnl_display.admin_order_field = 'total_pnl'

    def win_rate_display(self, obj):
        """Display win rate with color."""
        win_rate = float(obj.win_rate)
        if win_rate >= 70:
            color = 'green'
        elif win_rate >= 50:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            win_rate
        )
    win_rate_display.short_description = 'Win Rate'
    win_rate_display.admin_order_field = 'win_rate'

    def open_positions_count(self, obj):
        """Display open positions count."""
        count = len(obj.open_positions)
        if count > 0:
            return format_html('<strong>{}</strong>', count)
        return count
    open_positions_count.short_description = 'Open Positions'

    def auto_trading_status(self, obj):
        """Display auto-trading status."""
        if obj.auto_trading_enabled:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">ENABLED</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">DISABLED</span>'
            )
    auto_trading_status.short_description = 'Auto-Trading'
    auto_trading_status.admin_order_field = 'auto_trading_enabled'

    @admin.action(description='Reset accounts to initial state')
    def reset_accounts(self, request, queryset):
        """Bulk reset accounts."""
        for account in queryset:
            account.reset_account()
        self.message_user(request, f'{queryset.count()} accounts reset successfully.')

    @admin.action(description='Enable auto-trading')
    def enable_auto_trading(self, request, queryset):
        """Bulk enable auto-trading."""
        updated = queryset.update(auto_trading_enabled=True)
        self.message_user(request, f'Auto-trading enabled for {updated} accounts.')

    @admin.action(description='Disable auto-trading')
    def disable_auto_trading(self, request, queryset):
        """Bulk disable auto-trading."""
        updated = queryset.update(auto_trading_enabled=False)
        self.message_user(request, f'Auto-trading disabled for {updated} accounts.')

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related('user')



# Backtesting Admin

@admin.register(BacktestRun)
class BacktestRunAdmin(BaseModelAdmin):
    """Admin interface for Backtest Runs."""
    list_display = ("id", "name", "status", "user", "timeframe", "total_trades", "win_rate", "roi", "created_at")
    list_filter = ("status", "timeframe", "created_at")
    search_fields = ("name", "user__email")
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at", "duration_seconds",
                      "total_trades", "winning_trades", "losing_trades", "win_rate",
                      "total_profit_loss", "roi", "max_drawdown", "sharpe_ratio", "profit_factor")

@admin.register(BacktestTrade)
class BacktestTradeAdmin(admin.ModelAdmin):
    """Admin interface for Backtest Trades."""
    list_display = ("id", "backtest_run", "symbol", "direction", "entry_price", "exit_price",
                   "profit_loss", "profit_loss_percentage", "status", "opened_at")
    list_filter = ("direction", "status", "market_type", "opened_at")
    search_fields = ("symbol", "backtest_run__name")

@admin.register(StrategyOptimization)
class StrategyOptimizationAdmin(admin.ModelAdmin):
    """Admin interface for Strategy Optimizations."""
    list_display = ("id", "name", "timeframe", "optimization_score", "win_rate", "roi",
                   "total_trades", "tested_at")
    list_filter = ("timeframe", "tested_at")
    search_fields = ("name", "user__email")
    readonly_fields = ("tested_at", "optimization_score")
    ordering = ("-optimization_score", "-win_rate")
    date_hierarchy = 'tested_at'

@admin.register(OptimizationRecommendation)
class OptimizationRecommendationAdmin(BaseModelAdmin):
    """Admin interface for Optimization Recommendations."""
    list_display = ("id", "type", "title", "confidence_score", "status", "user", "created_at")
    list_filter = ("type", "status", "created_at")
    search_fields = ("title", "description", "user__email")

@admin.register(BacktestMetric)
class BacktestMetricAdmin(admin.ModelAdmin):
    """Admin interface for Backtest Metrics."""
    list_display = ("id", "backtest_run", "timestamp", "equity", "total_pnl", "open_trades")
    list_filter = ("backtest_run", "timestamp")


# Walk-Forward Optimization Admin

class WalkForwardWindowInline(admin.TabularInline):
    """Inline admin for Walk-Forward Windows."""
    model = WalkForwardWindow
    extra = 0
    fields = (
        'window_number', 'status',
        'in_sample_roi', 'out_sample_roi',
        'performance_drop_pct'
    )
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(WalkForwardOptimization)
class WalkForwardOptimizationAdmin(BaseModelAdmin):
    """Admin interface for Walk-Forward Optimization."""
    list_display = (
        "id", "name", "status", "user",
        "timeframe", "total_windows", "completed_windows",
        "progress_display", "robustness_badge",
        "avg_out_sample_roi", "consistency_score",
        "created_at"
    )
    list_filter = ("status", "is_robust", "timeframe", "created_at")
    search_fields = ("name", "user__email", "symbols")
    readonly_fields = (
        "created_at", "updated_at", "started_at", "completed_at",
        "total_windows", "completed_windows",
        "avg_in_sample_win_rate", "avg_out_sample_win_rate",
        "avg_in_sample_roi", "avg_out_sample_roi",
        "performance_degradation", "consistency_score",
        "is_robust", "robustness_notes"
    )
    inlines = [WalkForwardWindowInline]
    ordering = ("-created_at",)
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'user', 'status', 'error_message')
        }),
        ('Configuration', {
            'fields': (
                'symbols', 'timeframe', 'start_date', 'end_date',
                'training_window_days', 'testing_window_days', 'step_days',
                'optimization_method', 'parameter_ranges'
            )
        }),
        ('Trading Parameters', {
            'fields': ('initial_capital', 'position_size')
        }),
        ('Execution Info', {
            'fields': ('started_at', 'completed_at', 'total_windows', 'completed_windows')
        }),
        ('Aggregate Results', {
            'fields': (
                'avg_in_sample_win_rate', 'avg_out_sample_win_rate',
                'avg_in_sample_roi', 'avg_out_sample_roi',
                'performance_degradation', 'consistency_score'
            )
        }),
        ('Robustness Assessment', {
            'fields': ('is_robust', 'robustness_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def progress_display(self, obj):
        """Display progress as percentage."""
        if obj.total_windows == 0:
            return "-"
        pct = int((obj.completed_windows / obj.total_windows) * 100)
        color = "green" if pct == 100 else "orange" if pct > 0 else "gray"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{} ({}%)</span>',
            color, obj.completed_windows, obj.total_windows, pct
        )
    progress_display.short_description = 'Progress'

    def robustness_badge(self, obj):
        """Display robustness as colored badge."""
        if obj.status != 'COMPLETED':
            return format_html('<span style="color: gray;">-</span>')

        if obj.is_robust:
            return format_html(
                '<span style="background-color: #10b981; color: white; '
                'padding: 3px 8px; border-radius: 4px; font-weight: bold;">✓ ROBUST</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ef4444; color: white; '
                'padding: 3px 8px; border-radius: 4px; font-weight: bold;">✗ NOT ROBUST</span>'
            )
    robustness_badge.short_description = 'Robustness'


@admin.register(WalkForwardWindow)
class WalkForwardWindowAdmin(admin.ModelAdmin):
    """Admin interface for Walk-Forward Windows."""
    list_display = (
        "id", "walk_forward", "window_number", "status",
        "in_sample_roi_display", "out_sample_roi_display",
        "performance_drop_display",
        "training_period", "testing_period"
    )
    list_filter = ("status", "walk_forward__name", "window_number")
    search_fields = ("walk_forward__name",)
    readonly_fields = (
        "walk_forward", "window_number",
        "training_start", "training_end",
        "testing_start", "testing_end",
        "best_params",
        "in_sample_backtest_id", "in_sample_total_trades",
        "in_sample_win_rate", "in_sample_roi",
        "in_sample_sharpe", "in_sample_max_drawdown",
        "out_sample_backtest_id", "out_sample_total_trades",
        "out_sample_win_rate", "out_sample_roi",
        "out_sample_sharpe", "out_sample_max_drawdown",
        "performance_drop_pct",
        "created_at", "updated_at"
    )
    ordering = ("walk_forward", "window_number")

    fieldsets = (
        ('Window Information', {
            'fields': ('walk_forward', 'window_number', 'status', 'error_message')
        }),
        ('Date Ranges', {
            'fields': ('training_start', 'training_end', 'testing_start', 'testing_end')
        }),
        ('Optimization Results (In-Sample)', {
            'fields': (
                'in_sample_backtest_id', 'best_params',
                'in_sample_total_trades', 'in_sample_win_rate',
                'in_sample_roi', 'in_sample_sharpe', 'in_sample_max_drawdown'
            )
        }),
        ('Testing Results (Out-of-Sample)', {
            'fields': (
                'out_sample_backtest_id',
                'out_sample_total_trades', 'out_sample_win_rate',
                'out_sample_roi', 'out_sample_sharpe', 'out_sample_max_drawdown'
            )
        }),
        ('Performance Comparison', {
            'fields': ('performance_drop_pct',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def in_sample_roi_display(self, obj):
        """Format in-sample ROI with color."""
        roi = float(obj.in_sample_roi)
        color = "green" if roi > 0 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:+.2f}%</span>',
            color, roi
        )
    in_sample_roi_display.short_description = 'In-Sample ROI'

    def out_sample_roi_display(self, obj):
        """Format out-of-sample ROI with color."""
        roi = float(obj.out_sample_roi)
        color = "green" if roi > 0 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:+.2f}%</span>',
            color, roi
        )
    out_sample_roi_display.short_description = 'Out-Sample ROI'

    def performance_drop_display(self, obj):
        """Format performance drop with color."""
        drop = float(obj.performance_drop_pct)
        if drop < 30:
            color = "green"
        elif drop < 50:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, drop
        )
    performance_drop_display.short_description = 'Performance Drop'

    def training_period(self, obj):
        """Display training period."""
        return f"{obj.training_start.strftime('%Y-%m-%d')} to {obj.training_end.strftime('%Y-%m-%d')}"
    training_period.short_description = 'Training Period'

    def testing_period(self, obj):
        """Display testing period."""
        return f"{obj.testing_start.strftime('%Y-%m-%d')} to {obj.testing_end.strftime('%Y-%m-%d')}"
    testing_period.short_description = 'Testing Period'


@admin.register(WalkForwardMetric)
class WalkForwardMetricAdmin(admin.ModelAdmin):
    """Admin interface for Walk-Forward Metrics."""
    list_display = (
        "id", "walk_forward", "window_number", "window_type",
        "cumulative_roi", "cumulative_trades",
        "window_pnl", "timestamp"
    )
    list_filter = ("window_type", "walk_forward__name", "window_number")
    search_fields = ("walk_forward__name",)
    ordering = ("walk_forward", "window_number", "window_type")


# =============================================================================
# MONTE CARLO SIMULATION ADMIN
# =============================================================================

@admin.register(MonteCarloSimulation)
class MonteCarloSimulationAdmin(admin.ModelAdmin):
    """Admin interface for Monte Carlo Simulations."""
    list_display = (
        "id", "name", "user", "status", "symbols_display",
        "num_simulations", "progress_display",
        "mean_return_display", "probability_of_profit_display",
        "robustness_display", "created_at"
    )
    list_filter = ("status", "is_statistically_robust", "timeframe", "created_at")
    search_fields = ("name", "user__username", "symbols")
    readonly_fields = (
        "task_id", "completed_simulations", "failed_simulations",
        "mean_return", "median_return", "std_deviation", "variance",
        "confidence_95_lower", "confidence_95_upper",
        "confidence_99_lower", "confidence_99_upper",
        "probability_of_profit", "probability_of_loss",
        "value_at_risk_95", "value_at_risk_99",
        "best_case_return", "worst_case_return",
        "mean_max_drawdown", "worst_case_drawdown", "best_case_drawdown",
        "mean_sharpe_ratio", "median_sharpe_ratio",
        "mean_win_rate", "median_win_rate",
        "is_statistically_robust", "robustness_score", "robustness_reasons",
        "created_at", "started_at", "completed_at"
    )
    ordering = ("-created_at",)

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'user', 'status', 'error_message')
        }),
        ('Simulation Configuration', {
            'fields': (
                'symbols', 'timeframe', 'start_date', 'end_date',
                'num_simulations', 'strategy_params', 'randomization_config',
                'initial_capital', 'position_size'
            )
        }),
        ('Execution Progress', {
            'fields': ('task_id', 'completed_simulations', 'failed_simulations')
        }),
        ('Central Tendency', {
            'fields': ('mean_return', 'median_return'),
            'classes': ('collapse',)
        }),
        ('Dispersion', {
            'fields': ('std_deviation', 'variance'),
            'classes': ('collapse',)
        }),
        ('Confidence Intervals', {
            'fields': (
                'confidence_95_lower', 'confidence_95_upper',
                'confidence_99_lower', 'confidence_99_upper'
            ),
            'classes': ('collapse',)
        }),
        ('Probability Metrics', {
            'fields': ('probability_of_profit', 'probability_of_loss'),
            'classes': ('collapse',)
        }),
        ('Risk Metrics', {
            'fields': ('value_at_risk_95', 'value_at_risk_99'),
            'classes': ('collapse',)
        }),
        ('Extremes', {
            'fields': ('best_case_return', 'worst_case_return'),
            'classes': ('collapse',)
        }),
        ('Drawdown Statistics', {
            'fields': ('mean_max_drawdown', 'worst_case_drawdown', 'best_case_drawdown'),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': (
                'mean_sharpe_ratio', 'median_sharpe_ratio',
                'mean_win_rate', 'median_win_rate'
            ),
            'classes': ('collapse',)
        }),
        ('Robustness Assessment', {
            'fields': ('is_statistically_robust', 'robustness_score', 'robustness_reasons')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def symbols_display(self, obj):
        """Display symbols as comma-separated string."""
        return ", ".join(obj.symbols) if obj.symbols else "-"
    symbols_display.short_description = 'Symbols'

    def progress_display(self, obj):
        """Display progress with progress bar."""
        progress = obj.progress_percentage()
        if obj.status == 'COMPLETED':
            color = "green"
        elif obj.status == 'RUNNING':
            color = "blue"
        elif obj.status == 'FAILED':
            color = "red"
        else:
            color = "gray"

        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; '
            'text-align: center; color: white; font-weight: bold;">{}</div></div>',
            progress, color, f"{progress}%"
        )
    progress_display.short_description = 'Progress'

    def mean_return_display(self, obj):
        """Display mean return with color."""
        mean_ret = float(obj.mean_return)
        color = "green" if mean_ret > 0 else "red"
        sign = "+" if mean_ret >= 0 else ""
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{:.2f}%</span>',
            color, sign, mean_ret
        )
    mean_return_display.short_description = 'Mean Return'

    def probability_of_profit_display(self, obj):
        """Display probability of profit with color."""
        prob = float(obj.probability_of_profit)
        if prob >= 70:
            color = "green"
        elif prob >= 60:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, prob
        )
    probability_of_profit_display.short_description = 'Prob. of Profit'

    def robustness_display(self, obj):
        """Display robustness with badge."""
        score = float(obj.robustness_score)
        if score >= 80:
            color = "green"
            label = "ROBUST"
        elif score >= 60:
            color = "orange"
            label = "MODERATE"
        else:
            color = "red"
            label = "WEAK"

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span> ({})',
            color, label, score
        )
    robustness_display.short_description = 'Robustness'


@admin.register(MonteCarloRun)
class MonteCarloRunAdmin(admin.ModelAdmin):
    """Admin interface for Monte Carlo Runs."""
    list_display = (
        "id", "simulation", "run_number",
        "total_trades", "win_rate_display",
        "roi_display", "sharpe_ratio",
        "created_at"
    )
    list_filter = ("simulation__name", "simulation__status")
    search_fields = ("simulation__name",)
    ordering = ("simulation", "run_number")

    fieldsets = (
        ('Run Information', {
            'fields': ('simulation', 'run_number', 'parameters_used')
        }),
        ('Performance', {
            'fields': (
                'total_trades', 'winning_trades', 'losing_trades', 'win_rate',
                'total_profit_loss', 'roi'
            )
        }),
        ('Risk Metrics', {
            'fields': (
                'max_drawdown', 'max_drawdown_amount',
                'sharpe_ratio', 'profit_factor'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def roi_display(self, obj):
        """Display ROI with color."""
        roi = float(obj.roi)
        color = "green" if roi > 0 else "red"
        sign = "+" if roi >= 0 else ""
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{:.2f}%</span>',
            color, sign, roi
        )
    roi_display.short_description = 'ROI'

    def win_rate_display(self, obj):
        """Display win rate with color."""
        wr = float(obj.win_rate)
        if wr >= 60:
            color = "green"
        elif wr >= 50:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, wr
        )
    win_rate_display.short_description = 'Win Rate'


@admin.register(MonteCarloDistribution)
class MonteCarloDistributionAdmin(admin.ModelAdmin):
    """Admin interface for Monte Carlo Distributions."""
    list_display = (
        "id", "simulation", "metric",
        "mean", "median", "std_dev",
        "percentile_5", "percentile_95"
    )
    list_filter = ("metric", "simulation__name")
    search_fields = ("simulation__name",)
    ordering = ("simulation", "metric")


# =============================================================================
# ML-BASED TUNING ADMIN
# =============================================================================

@admin.register(MLTuningJob)
class MLTuningJobAdmin(admin.ModelAdmin):
    """Admin interface for ML Tuning Jobs."""
    list_display = (
        "id", "name", "user", "status", "ml_algorithm",
        "optimization_metric", "progress_display",
        "training_score", "validation_score",
        "quality_display", "is_production_ready",
        "created_at"
    )
    list_filter = ("status", "ml_algorithm", "optimization_metric", "is_production_ready")
    search_fields = ("name", "user__username")
    readonly_fields = (
        "task_id", "samples_evaluated", "samples_successful", "samples_failed",
        "training_score", "validation_score", "test_score",
        "best_parameters", "predicted_performance",
        "out_of_sample_roi", "out_of_sample_sharpe",
        "out_of_sample_win_rate", "out_of_sample_max_drawdown",
        "feature_importance", "parameter_sensitivity",
        "model_file_path", "scaler_file_path",
        "overfitting_score", "model_confidence",
        "is_production_ready",
        "created_at", "started_at", "completed_at"
    )
    ordering = ("-created_at",)

    def progress_display(self, obj):
        """Display progress with progress bar."""
        progress = obj.progress_percentage()
        if obj.status == 'COMPLETED':
            color = "green"
        elif obj.status == 'RUNNING':
            color = "blue"
        elif obj.status == 'FAILED':
            color = "red"
        else:
            color = "gray"

        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; '
            'text-align: center; color: white; font-weight: bold;">{}</div></div>',
            progress, color, f"{progress}%"
        )
    progress_display.short_description = 'Progress'

    def quality_display(self, obj):
        """Display quality score with badge."""
        score = float(obj.model_confidence)
        if score >= 80:
            color = "green"
            label = "EXCELLENT"
        elif score >= 60:
            color = "orange"
            label = "GOOD"
        elif score >= 40:
            color = "gray"
            label = "FAIR"
        else:
            color = "red"
            label = "POOR"

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span> ({:.0f})',
            color, label, score
        )
    quality_display.short_description = 'Quality'


@admin.register(MLTuningSample)
class MLTuningSampleAdmin(admin.ModelAdmin):
    """Admin interface for ML Tuning Samples."""
    list_display = (
        "id", "tuning_job", "sample_number", "split_set",
        "target_value", "roi", "sharpe_ratio",
        "win_rate", "total_trades"
    )
    list_filter = ("split_set", "tuning_job__name")
    search_fields = ("tuning_job__name",)
    ordering = ("tuning_job", "sample_number")


@admin.register(MLPrediction)
class MLPredictionAdmin(admin.ModelAdmin):
    """Admin interface for ML Predictions."""
    list_display = (
        "id", "tuning_job", "predicted_value",
        "prediction_confidence", "actual_value",
        "prediction_error", "created_at"
    )
    list_filter = ("tuning_job__name",)
    search_fields = ("tuning_job__name",)
    ordering = ("-created_at",)


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    """Admin interface for ML Models."""
    list_display = (
        "id", "name", "user", "ml_algorithm",
        "training_score", "validation_score",
        "is_production_ready", "is_active",
        "times_used", "created_at"
    )
    list_filter = ("ml_algorithm", "is_production_ready", "is_active")
    search_fields = ("name", "user__username")
    ordering = ("-created_at",)

