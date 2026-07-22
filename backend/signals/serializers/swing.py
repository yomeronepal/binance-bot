"""Serializers for the 4h swing engine."""
from rest_framework import serializers

from signals.models.swing import SwingPaperTrade, SwingSignal


class SwingSignalSerializer(serializers.ModelSerializer):
    """A detected 4h breakout signal."""

    risk_reward_ratio = serializers.FloatField(read_only=True)

    class Meta:
        model = SwingSignal
        fields = [
            'id', 'symbol', 'direction', 'entry_timeframe', 'trend_timeframe',
            'candle_open_time', 'entry', 'stop_loss', 'take_profit', 'atr',
            'status', 'risk_reward_ratio', 'meta', 'created_at',
        ]


class SwingPaperTradeSerializer(serializers.ModelSerializer):
    """Swing paper trade with net-of-fee P/L."""

    class Meta:
        model = SwingPaperTrade
        fields = [
            'id', 'symbol', 'direction', 'entry_price', 'stop_loss', 'take_profit',
            'atr_at_entry', 'quantity', 'position_size', 'leverage',
            'entry_time', 'exit_price', 'exit_time', 'status',
            'profit_loss', 'fees_paid', 'profit_loss_percentage', 'created_at',
        ]
