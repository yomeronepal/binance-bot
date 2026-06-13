"""
Serializers for blacklist functionality.
"""
from rest_framework import serializers
from signals.models.blacklist import BlacklistedSymbol


class BlacklistedSymbolSerializer(serializers.ModelSerializer):
    """Serializer for blacklisted symbols."""

    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = BlacklistedSymbol
        fields = [
            'id',
            'symbol',
            'reason',
            'reason_display',
            'notes',
            'blacklisted_at',
            'blacklisted_until',
            'is_expired',
            'active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_symbol(self, value):
        """Validate and normalize symbol."""
        # Convert to uppercase
        value = value.upper().strip()

        # Basic validation
        if not value:
            raise serializers.ValidationError("Symbol cannot be empty.")

        if len(value) < 3:
            raise serializers.ValidationError("Symbol must be at least 3 characters.")

        # Check if already blacklisted (on create)
        if not self.instance:  # Creating new
            if BlacklistedSymbol.is_blacklisted(value):
                raise serializers.ValidationError(
                    f"Symbol {value} is already blacklisted."
                )

        return value


class BlacklistCheckSerializer(serializers.Serializer):
    """Serializer for checking if symbols are blacklisted."""
    symbols = serializers.ListField(
        child=serializers.CharField(max_length=20),
        help_text="List of symbols to check"
    )

    def validate_symbols(self, value):
        """Validate symbols list."""
        if not value:
            raise serializers.ValidationError("Symbols list cannot be empty.")

        # Normalize symbols
        return [s.upper().strip() for s in value]
