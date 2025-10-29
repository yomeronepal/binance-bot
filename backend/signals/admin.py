"""
Signal admin configuration following DRY principles.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Symbol, Signal, UserSubscription, PaperTrade, PaperAccount


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
