"""
Signal serializers following DRY principles and clean architecture.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Symbol, Signal, UserSubscription


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
