"""Serializers for the 4h order-block engine."""
from rest_framework import serializers

from signals.models.order_block import OrderBlockPaperTrade, OrderBlockSignal


class OrderBlockSignalSerializer(serializers.ModelSerializer):
    """A detected 4h order-block signal."""

    risk_reward_ratio = serializers.FloatField(read_only=True)

    class Meta:
        model = OrderBlockSignal
        fields = [
            'id', 'symbol', 'direction', 'entry_timeframe',
            'candle_open_time', 'entry', 'stop_loss', 'take_profit', 'atr',
            'confidence', 'structure', 'status', 'risk_reward_ratio',
            'meta', 'created_at',
        ]


class OrderBlockPaperTradeSerializer(serializers.ModelSerializer):
    """Order-block paper trade with net-of-fee P/L."""

    class Meta:
        model = OrderBlockPaperTrade
        fields = [
            'id', 'symbol', 'direction', 'entry_price', 'stop_loss', 'take_profit',
            'atr_at_entry', 'quantity', 'position_size', 'risk_amount', 'confidence',
            'leverage', 'entry_time', 'exit_price', 'exit_time', 'status',
            'profit_loss', 'fees_paid', 'profit_loss_percentage', 'created_at',
        ]
