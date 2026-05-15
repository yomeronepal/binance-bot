"""
Serializers for Futures Trading models.
"""
from rest_framework import serializers
from .models_futures import FuturesTradingSettings, FuturesTrade


class FuturesTradingSettingsSerializer(serializers.ModelSerializer):
    """Serializer for FuturesTradingSettings model."""

    effective_position_size = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = FuturesTradingSettings
        fields = [
            'id',
            'is_enabled',
            'trade_amount',
            'leverage',
            'max_concurrent_trades',
            'min_signal_confidence',
            'allowed_symbols',
            'trade_long',
            'trade_short',
            'use_trading_window',
            'macro_filter_enabled',
            'crypto_macro_filter_enabled',
            'stock_macro_filter_enabled',
            'commodity_macro_filter_enabled',
            'total_trading_capital',
            'last_balance_updated_at',
            'effective_position_size',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'effective_position_size']


class FuturesTradeSerializer(serializers.ModelSerializer):
    """Full serializer for FuturesTrade model."""

    signal_id = serializers.IntegerField(source='signal.id', read_only=True, allow_null=True)
    is_open = serializers.BooleanField(read_only=True)
    is_closed = serializers.BooleanField(read_only=True)
    is_profitable = serializers.BooleanField(read_only=True)
    is_priority = serializers.SerializerMethodField()

    class Meta:
        model = FuturesTrade
        fields = [
            'id',
            'signal_id',
            'symbol',
            'direction',
            'leverage',
            'quantity',
            'entry_price',
            'stop_loss',
            'take_profit',
            'exit_price',
            'position_size_usdt',
            'profit_loss',
            'profit_loss_percentage',
            'mark_price',
            'unrealized_pnl',
            'unrealized_pnl_percentage',
            'liquidation_price',
            'margin_type',
            'last_sync_time',
            'status',
            'binance_order_id',
            'binance_exit_order_id',
            'error_message',
            'entry_time',
            'exit_time',
            'is_open',
            'is_closed',
            'is_profitable',
            'is_priority',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_is_priority(self, obj):
        """Get priority flag from the associated signal."""
        if obj.signal_id:
            return getattr(obj.signal, 'is_priority', False)
        return False


class FuturesTradeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for trade lists with live data."""

    is_priority = serializers.SerializerMethodField()

    class Meta:
        model = FuturesTrade
        fields = [
            'id',
            'symbol',
            'direction',
            'leverage',
            'entry_price',
            'exit_price',
            'profit_loss',
            'profit_loss_percentage',
            'mark_price',
            'unrealized_pnl',
            'unrealized_pnl_percentage',
            'liquidation_price',
            'last_sync_time',
            'status',
            'entry_time',
            'exit_time',
            'is_priority',
            'created_at',
        ]

    def get_is_priority(self, obj):
        """Get priority flag from the associated signal."""
        if obj.signal_id:
            return getattr(obj.signal, 'is_priority', False)
        return False
