"""Serializers for the day-trade (15m Market Structure) system."""
from rest_framework import serializers

from signals.models.daytrade import (
    DayTradeSignal,
    DayTradePaperTrade,
    DayTradeTradeExit,
    DayTradePaperAccount,
)


class DayTradeSignalSerializer(serializers.ModelSerializer):
    """Day-trade signal with the ATR-derived exit map."""

    risk_reward_ratio = serializers.FloatField(read_only=True)

    class Meta:
        model = DayTradeSignal
        fields = [
            'id', 'symbol', 'direction', 'entry_timeframe', 'trend_timeframe',
            'candle_open_time', 'entry', 'stop_loss', 'tp1', 'tp2', 'atr',
            'confidence', 'score', 'risk_reward_ratio', 'market_type',
            'leverage', 'status', 'source', 'meta',
            'created_at', 'expires_at',
        ]


class DayTradeTradeExitSerializer(serializers.ModelSerializer):
    """A single scale-out leg of a day-trade."""

    class Meta:
        model = DayTradeTradeExit
        fields = ['id', 'exit_type', 'price', 'quantity', 'pnl', 'exit_time']


class DayTradePaperTradeSerializer(serializers.ModelSerializer):
    """Day-trade paper position with nested scale-out legs."""

    exits = DayTradeTradeExitSerializer(many=True, read_only=True)
    duration_hours = serializers.FloatField(read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    is_closed = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = DayTradePaperTrade
        fields = [
            'id', 'signal', 'symbol', 'direction', 'market_type', 'timeframe',
            'confidence', 'entry_price', 'entry_time', 'position_size',
            'quantity', 'remaining_quantity',
            'initial_stop_loss', 'stop_loss', 'trailing_stop',
            'tp1_price', 'tp2_price', 'atr_at_entry', 'tp1_filled', 'tp2_filled',
            'account_risk_pct', 'stop_distance',
            'exit_price', 'exit_time',
            'realized_pnl', 'profit_loss', 'profit_loss_percentage',
            'leverage', 'status', 'duration_hours', 'is_open', 'is_closed',
            'exits', 'created_at',
        ]


class DayTradePaperAccountSerializer(serializers.ModelSerializer):
    """Day-trade bot account snapshot."""

    class Meta:
        model = DayTradePaperAccount
        fields = [
            'id', 'initial_balance', 'balance', 'equity',
            'total_pnl', 'realized_pnl', 'unrealized_pnl',
            'total_trades', 'winning_trades', 'losing_trades', 'win_rate',
            'risk_per_trade_pct', 'max_open_trades',
            'last_trade_at', 'updated_at',
        ]
