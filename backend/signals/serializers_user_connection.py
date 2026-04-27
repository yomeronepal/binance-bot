"""
Serializers for the per-user Binance connection API.

Connect input is intentionally minimal — only the api_key/api_secret. The
output never includes any portion of the secret, and the api_key is
truncated to a hint suitable for display.
"""
from rest_framework import serializers

from .models_user_connection import UserBinanceConnection


class UserBinanceConnectionStateSerializer(serializers.ModelSerializer):
    """Read-only state of the current user's connection (no secrets)."""

    class Meta:
        model = UserBinanceConnection
        fields = [
            'status', 'api_key_hint', 'permissions',
            'ip_check_passed', 'last_check_at', 'last_error',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class UserBinanceConnectInputSerializer(serializers.Serializer):
    """Body for POST /api/binance/connect."""
    api_key = serializers.CharField(
        min_length=10, max_length=128, trim_whitespace=True,
    )
    api_secret = serializers.CharField(
        min_length=10, max_length=256, trim_whitespace=True,
    )

    def validate_api_key(self, value):
        if any(c.isspace() for c in value):
            raise serializers.ValidationError("API key must not contain whitespace.")
        return value

    def validate_api_secret(self, value):
        if any(c.isspace() for c in value):
            raise serializers.ValidationError("API secret must not contain whitespace.")
        return value
