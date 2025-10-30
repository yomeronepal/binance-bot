"""
Signal serializers following DRY principles and clean architecture.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Symbol, Signal, UserSubscription, PaperTrade, PaperAccount
from .models_optimization import StrategyConfigHistory, OptimizationRun, TradeCounter


User = get_user_model()


class BaseModelSerializer(serializers.ModelSerializer):
    """
    Base serializer with common fields and behaviors.
    Implements DRY principle for timestamp fields.
    """
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    updated_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")


class SymbolSerializer(BaseModelSerializer):
    """
    Symbol serializer with validation and additional computed fields.
    """
    signals_count = serializers.SerializerMethodField()

    class Meta:
        model = Symbol
        fields = [
            'id',
            'symbol',
            'exchange',
            'active',
            'signals_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_signals_count(self, obj):
        """Get count of active signals for this symbol."""
        return obj.signals.filter(status='ACTIVE').count()

    def validate_symbol(self, value):
        """Validate symbol format (e.g., BTCUSDT)."""
        value = value.upper().strip()
        if len(value) < 3:
            raise serializers.ValidationError("Symbol must be at least 3 characters long.")
        if not value.isalnum():
            raise serializers.ValidationError("Symbol must contain only alphanumeric characters.")
        return value

    def validate_exchange(self, value):
        """Validate exchange name."""
        value = value.upper().strip()
        valid_exchanges = ['BINANCE', 'COINBASE', 'KRAKEN', 'BYBIT', 'KUCOIN']
        if value not in valid_exchanges:
            raise serializers.ValidationError(
                f"Invalid exchange. Must be one of: {', '.join(valid_exchanges)}"
            )
        return value


class SymbolListSerializer(serializers.ModelSerializer):
    """
    Lightweight symbol serializer for nested representations.
    """
    class Meta:
        model = Symbol
        fields = ['id', 'symbol', 'exchange']


class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic user serializer for nested representations.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email']
        read_only_fields = fields


class SignalSerializer(BaseModelSerializer):
    """
    Comprehensive signal serializer with nested symbol and validation.
    """
    # Nested representations
    symbol_detail = SymbolListSerializer(source='symbol', read_only=True)
    created_by_detail = UserBasicSerializer(source='created_by', read_only=True)

    # Write-only field for symbol (accepts ID or symbol string)
    symbol_id = serializers.IntegerField(write_only=True, required=False)
    symbol_name = serializers.CharField(write_only=True, required=False)

    # Computed fields
    risk_reward_ratio = serializers.SerializerMethodField()
    profit_percentage = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)

    class Meta:
        model = Signal
        fields = [
            'id',
            'symbol',
            'symbol_id',
            'symbol_name',
            'symbol_detail',
            'direction',
            'direction_display',
            'timeframe',
            'entry',
            'sl',
            'tp',
            'confidence',
            'source',
            'status',
            'status_display',
            'meta',
            'description',
            'created_by',
            'created_by_detail',
            'risk_reward_ratio',
            'profit_percentage',
            'expires_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_risk_reward_ratio(self, obj):
        """Get risk/reward ratio."""
        return obj.risk_reward_ratio

    def get_profit_percentage(self, obj):
        """Calculate potential profit percentage."""
        entry = float(obj.entry)
        tp = float(obj.tp)

        if obj.direction == 'LONG':
            profit_pct = ((tp - entry) / entry) * 100
        else:  # SHORT
            profit_pct = ((entry - tp) / entry) * 100

        return round(profit_pct, 2)

    def validate(self, attrs):
        """
        Validate signal data ensuring logical price relationships.
        """
        # Get or create symbol
        symbol_id = attrs.pop('symbol_id', None)
        symbol_name = attrs.pop('symbol_name', None)

        if symbol_id:
            try:
                attrs['symbol'] = Symbol.objects.get(id=symbol_id)
            except Symbol.DoesNotExist:
                raise serializers.ValidationError({"symbol_id": "Symbol not found."})
        elif symbol_name:
            symbol, _ = Symbol.objects.get_or_create(
                symbol=symbol_name.upper(),
                defaults={'exchange': 'BINANCE', 'active': True}
            )
            attrs['symbol'] = symbol

        # Validate price relationships
        entry = attrs.get('entry')
        sl = attrs.get('sl')
        tp = attrs.get('tp')
        direction = attrs.get('direction')

        if entry and sl and tp and direction:
            if direction == 'LONG':
                if sl >= entry:
                    raise serializers.ValidationError({
                        "sl": "Stop loss must be below entry price for LONG signals."
                    })
                if tp <= entry:
                    raise serializers.ValidationError({
                        "tp": "Take profit must be above entry price for LONG signals."
                    })
            else:  # SHORT
                if sl <= entry:
                    raise serializers.ValidationError({
                        "sl": "Stop loss must be above entry price for SHORT signals."
                    })
                if tp >= entry:
                    raise serializers.ValidationError({
                        "tp": "Take profit must be below entry price for SHORT signals."
                    })

        # Validate confidence
        confidence = attrs.get('confidence', 0.5)
        if not (0.0 <= confidence <= 1.0):
            raise serializers.ValidationError({
                "confidence": "Confidence must be between 0.0 and 1.0."
            })

        return attrs

    def validate_entry(self, value):
        """Validate entry price."""
        if value <= 0:
            raise serializers.ValidationError("Entry price must be greater than 0.")
        return value

    def validate_sl(self, value):
        """Validate stop loss price."""
        if value <= 0:
            raise serializers.ValidationError("Stop loss must be greater than 0.")
        return value

    def validate_tp(self, value):
        """Validate take profit price."""
        if value <= 0:
            raise serializers.ValidationError("Take profit must be greater than 0.")
        return value

    def create(self, validated_data):
        """Create signal with current user as creator."""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class SignalListSerializer(serializers.ModelSerializer):
    """
    Lightweight signal serializer for list views.
    Optimized for performance with minimal fields.
    """
    symbol_name = serializers.CharField(source='symbol.symbol', read_only=True)
    risk_reward = serializers.SerializerMethodField()

    class Meta:
        model = Signal
        fields = [
            'id',
            'symbol_name',
            'direction',
            'entry',
            'sl',
            'tp',
            'confidence',
            'status',
            'risk_reward',
            'created_at',
            'market_type',
            'leverage',
            'timeframe',
            'description',
            'trading_type',
            'estimated_duration_hours'
        ]

    def get_risk_reward(self, obj):
        """Get risk/reward ratio."""
        return obj.risk_reward_ratio


class UserSubscriptionSerializer(BaseModelSerializer):
    """
    User subscription serializer with computed fields.
    """
    user_detail = UserBasicSerializer(source='user', read_only=True)
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # Computed fields
    is_premium = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    signal_limit = serializers.SerializerMethodField()
    can_access_advanced = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'id',
            'user',
            'user_detail',
            'tier',
            'tier_display',
            'status',
            'status_display',
            'stripe_customer_id',
            'stripe_subscription_id',
            'is_premium',
            'is_active',
            'signal_limit',
            'can_access_advanced',
            'expires_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
        extra_kwargs = {
            'stripe_customer_id': {'write_only': True},
            'stripe_subscription_id': {'write_only': True},
        }

    def get_signal_limit(self, obj):
        """Get signal limit based on tier."""
        return obj.get_signal_limit()

    def get_can_access_advanced(self, obj):
        """Check if user can access advanced features."""
        return obj.can_access_advanced_features()

    def validate_tier(self, value):
        """Validate subscription tier."""
        valid_tiers = ['free', 'pro', 'premium']
        if value not in valid_tiers:
            raise serializers.ValidationError(
                f"Invalid tier. Must be one of: {', '.join(valid_tiers)}"
            )
        return value

    def validate(self, attrs):
        """Validate subscription data."""
        tier = attrs.get('tier')
        stripe_customer_id = attrs.get('stripe_customer_id')
        stripe_subscription_id = attrs.get('stripe_subscription_id')

        # Paid tiers require Stripe IDs
        if tier in ['pro', 'premium']:
            if not stripe_customer_id or not stripe_subscription_id:
                raise serializers.ValidationError({
                    "stripe_customer_id": "Stripe customer ID required for paid tiers.",
                    "stripe_subscription_id": "Stripe subscription ID required for paid tiers."
                })

        return attrs


# Bulk operations serializers
class BulkSignalCreateSerializer(serializers.Serializer):
    """
    Serializer for creating multiple signals at once.
    """
    signals = SignalSerializer(many=True)

    def create(self, validated_data):
        """Create multiple signals."""
        signals_data = validated_data.get('signals', [])
        signals = [Signal(**signal_data) for signal_data in signals_data]
        return Signal.objects.bulk_create(signals)


class SignalStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk status updates.
    """
    signal_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    status = serializers.ChoiceField(choices=Signal.STATUS_CHOICES)

    def update(self, instance, validated_data):
        """Update status for multiple signals."""
        signal_ids = validated_data.get('signal_ids', [])
        status = validated_data.get('status')

        Signal.objects.filter(id__in=signal_ids).update(status=status)
        return Signal.objects.filter(id__in=signal_ids)


class PaperTradeSerializer(BaseModelSerializer):
    """
    Paper trade serializer with computed fields and signal details.
    """
    signal_id = serializers.IntegerField(source='signal.id', read_only=True)
    signal_direction = serializers.CharField(source='signal.direction', read_only=True)
    signal_timeframe = serializers.CharField(source='signal.timeframe', read_only=True)
    signal_confidence = serializers.FloatField(source='signal.confidence', read_only=True)

    # Computed properties
    duration_hours = serializers.FloatField(read_only=True)
    risk_reward_ratio = serializers.FloatField(read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    is_closed = serializers.BooleanField(read_only=True)
    is_profitable = serializers.BooleanField(read_only=True)

    # Formatted fields
    entry_price_formatted = serializers.SerializerMethodField()
    exit_price_formatted = serializers.SerializerMethodField()
    profit_loss_formatted = serializers.SerializerMethodField()

    class Meta:
        model = PaperTrade
        fields = [
            'id', 'signal_id', 'signal_direction', 'signal_timeframe', 'signal_confidence',
            'symbol', 'direction', 'market_type',
            'entry_price', 'entry_price_formatted', 'entry_time',
            'position_size', 'quantity',
            'stop_loss', 'take_profit',
            'exit_price', 'exit_price_formatted', 'exit_time',
            'profit_loss', 'profit_loss_formatted', 'profit_loss_percentage',
            'leverage', 'status',
            'created_at', 'updated_at',
            'duration_hours', 'risk_reward_ratio',
            'is_open', 'is_closed', 'is_profitable'
        ]
        read_only_fields = [
            'id', 'entry_time', 'exit_price', 'exit_time',
            'profit_loss', 'profit_loss_percentage', 'status',
            'created_at', 'updated_at', 'quantity'
        ]

    def get_entry_price_formatted(self, obj):
        """Format entry price for display."""
        return f"${float(obj.entry_price):,.4f}"

    def get_exit_price_formatted(self, obj):
        """Format exit price for display."""
        if obj.exit_price:
            return f"${float(obj.exit_price):,.4f}"
        return None

    def get_profit_loss_formatted(self, obj):
        """Format P/L for display."""
        pnl = float(obj.profit_loss)
        sign = "+" if pnl >= 0 else ""
        return f"{sign}${pnl:,.2f}"


class PaperAccountSerializer(BaseModelSerializer):
    """
    Paper account serializer for auto-trading accounts.
    Includes balance, equity, performance metrics, and settings.
    """
    user_detail = UserBasicSerializer(source='user', read_only=True)

    # Computed fields
    available_balance = serializers.SerializerMethodField()
    open_positions_count = serializers.SerializerMethodField()
    equity_percentage = serializers.SerializerMethodField()
    balance_percentage = serializers.SerializerMethodField()

    # Formatted fields
    balance_formatted = serializers.SerializerMethodField()
    equity_formatted = serializers.SerializerMethodField()
    total_pnl_formatted = serializers.SerializerMethodField()
    realized_pnl_formatted = serializers.SerializerMethodField()
    unrealized_pnl_formatted = serializers.SerializerMethodField()

    class Meta:
        model = PaperAccount
        fields = [
            'id',
            'user',
            'user_detail',
            # Balances
            'initial_balance',
            'balance',
            'balance_formatted',
            'balance_percentage',
            'equity',
            'equity_formatted',
            'equity_percentage',
            'available_balance',
            # Performance metrics
            'total_pnl',
            'total_pnl_formatted',
            'realized_pnl',
            'realized_pnl_formatted',
            'unrealized_pnl',
            'unrealized_pnl_formatted',
            # Statistics
            'total_trades',
            'winning_trades',
            'losing_trades',
            'win_rate',
            # Risk management
            'max_position_size',
            'max_open_trades',
            # Auto-trading settings
            'auto_trading_enabled',
            'auto_trade_spot',
            'auto_trade_futures',
            'min_signal_confidence',
            # Open positions
            'open_positions',
            'open_positions_count',
            # Timestamps
            'last_trade_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
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
            'last_trade_at',
            'created_at',
            'updated_at',
        ]

    def get_available_balance(self, obj):
        """Calculate available balance (balance - allocated in positions)."""
        return float(obj.balance)

    def get_open_positions_count(self, obj):
        """Get count of open positions."""
        return len(obj.open_positions)

    def get_equity_percentage(self, obj):
        """Get equity as percentage of initial balance."""
        if obj.initial_balance > 0:
            return round((float(obj.equity) / float(obj.initial_balance)) * 100, 2)
        return 0.0

    def get_balance_percentage(self, obj):
        """Get balance as percentage of initial balance."""
        if obj.initial_balance > 0:
            return round((float(obj.balance) / float(obj.initial_balance)) * 100, 2)
        return 0.0

    def get_balance_formatted(self, obj):
        """Format balance for display."""
        return f"${float(obj.balance):,.2f}"

    def get_equity_formatted(self, obj):
        """Format equity for display."""
        return f"${float(obj.equity):,.2f}"

    def get_total_pnl_formatted(self, obj):
        """Format total P/L for display."""
        pnl = float(obj.total_pnl)
        sign = "+" if pnl >= 0 else ""
        return f"{sign}${pnl:,.2f}"

    def get_realized_pnl_formatted(self, obj):
        """Format realized P/L for display."""
        pnl = float(obj.realized_pnl)
        sign = "+" if pnl >= 0 else ""
        return f"{sign}${pnl:,.2f}"

    def get_unrealized_pnl_formatted(self, obj):
        """Format unrealized P/L for display."""
        pnl = float(obj.unrealized_pnl)
        sign = "+" if pnl >= 0 else ""
        return f"{sign}${pnl:,.2f}"

    def validate_max_position_size(self, value):
        """Validate max position size percentage."""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Max position size must be between 1% and 100%")
        return value

    def validate_max_open_trades(self, value):
        """Validate max open trades."""
        if value < 1 or value > 50:
            raise serializers.ValidationError("Max open trades must be between 1 and 50")
        return value

    def validate_min_signal_confidence(self, value):
        """Validate minimum signal confidence."""
        if value < 0 or value > 1:
            raise serializers.ValidationError("Minimum confidence must be between 0.0 and 1.0")
        return value


# =============================================================================
# OPTIMIZATION SERIALIZERS (Phase 6 - Auto-Optimization)
# =============================================================================

class StrategyConfigHistorySerializer(BaseModelSerializer):
    """Serializer for strategy configuration history with fitness scoring."""
    fitness_score = serializers.SerializerMethodField()
    baseline_config_name = serializers.SerializerMethodField()

    class Meta:
        model = StrategyConfigHistory
        fields = [
            "id",
            "config_name",
            "volatility_level",
            "version",
            "parameters",
            "metrics",
            "improved",
            "improvement_percentage",
            "baseline_config",
            "baseline_config_name",
            "status",
            "applied_at",
            "trades_evaluated",
            "fitness_score",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "version", "fitness_score"]

    def get_fitness_score(self, obj):
        """Calculate and return fitness score."""
        return obj.calculate_fitness_score()

    def get_baseline_config_name(self, obj):
        """Get baseline config name if exists."""
        if obj.baseline_config:
            return obj.baseline_config.config_name
        return None


class OptimizationRunSerializer(BaseModelSerializer):
    """Serializer for optimization run details."""
    baseline_config_name = serializers.SerializerMethodField()
    winning_config_name = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()

    class Meta:
        model = OptimizationRun
        fields = [
            "id",
            "run_id",
            "volatility_level",
            "trigger",
            "status",
            "baseline_config",
            "baseline_config_name",
            "baseline_score",
            "winning_config",
            "winning_config_name",
            "winning_score",
            "improvement_percentage",
            "improvement_found",
            "candidates_tested",
            "trades_analyzed",
            "lookback_days",
            "error_message",
            "started_at",
            "completed_at",
            "duration_seconds",
            "duration_formatted",
            "created_at",
        ]
        read_only_fields = ["id", "run_id", "created_at"]

    def get_baseline_config_name(self, obj):
        """Get baseline config name."""
        if obj.baseline_config:
            return obj.baseline_config.config_name
        return None

    def get_winning_config_name(self, obj):
        """Get winning config name."""
        if obj.winning_config:
            return obj.winning_config.config_name
        return None

    def get_duration_formatted(self, obj):
        """Format duration as human-readable string."""
        if obj.duration_seconds:
            minutes = obj.duration_seconds // 60
            seconds = obj.duration_seconds % 60
            return f"{minutes}m {seconds}s"
        return None


class TradeCounterSerializer(BaseModelSerializer):
    """Serializer for trade counter status."""
    percentage_complete = serializers.SerializerMethodField()
    trades_remaining = serializers.SerializerMethodField()

    class Meta:
        model = TradeCounter
        fields = [
            "id",
            "volatility_level",
            "trade_count",
            "threshold",
            "percentage_complete",
            "trades_remaining",
            "last_reset",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_percentage_complete(self, obj):
        """Calculate percentage towards threshold."""
        if obj.threshold > 0:
            return round((obj.trade_count / obj.threshold) * 100, 1)
        return 0.0

    def get_trades_remaining(self, obj):
        """Calculate trades remaining until threshold."""
        return max(0, obj.threshold - obj.trade_count)
