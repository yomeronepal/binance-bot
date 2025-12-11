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
            'status',
            'binance_order_id',
            'binance_exit_order_id',
            'error_message',
            'entry_time',
            'exit_time',
            'is_open',
            'is_closed',
            'is_profitable',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class FuturesTradeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for trade lists."""

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
            'status',
            'entry_time',
            'exit_time',
            'created_at',
        ]
