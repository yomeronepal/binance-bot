"""
API views for symbol blacklist management.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db import models
from signals.models.blacklist import BlacklistedSymbol
from signals.serializers.blacklist import BlacklistedSymbolSerializer, BlacklistCheckSerializer


class BlacklistedSymbolViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing blacklisted symbols.

    Endpoints:
    - GET /api/blacklist/ - List all blacklisted symbols
    - POST /api/blacklist/ - Create new blacklist entry
    - GET /api/blacklist/{id}/ - Retrieve blacklist entry
    - PUT /api/blacklist/{id}/ - Update blacklist entry
    - PATCH /api/blacklist/{id}/ - Partial update
    - DELETE /api/blacklist/{id}/ - Delete blacklist entry
    - POST /api/blacklist/check/ - Check if symbols are blacklisted
    - GET /api/blacklist/active/ - Get active blacklisted symbols
    """
    queryset = BlacklistedSymbol.objects.all()
    serializer_class = BlacklistedSymbolSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset based on query params."""
        queryset = super().get_queryset()

        # Filter by active status
        active = self.request.query_params.get('active')
        if active is not None:
            queryset = queryset.filter(active=active.lower() == 'true')

        # Filter by reason
        reason = self.request.query_params.get('reason')
        if reason:
            queryset = queryset.filter(reason=reason)

        # Filter by symbol
        symbol = self.request.query_params.get('symbol')
        if symbol:
            queryset = queryset.filter(symbol__icontains=symbol)

        # Filter expired
        include_expired = self.request.query_params.get('include_expired', 'true')
        if include_expired.lower() == 'false':
            now = timezone.now()
            queryset = queryset.filter(
                models.Q(blacklisted_until__isnull=True) |
                models.Q(blacklisted_until__gt=now)
            )

        return queryset.order_by('-blacklisted_at')

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def check(self, request):
        """
        Check if symbols are blacklisted.

        POST /api/blacklist/check/
        Body: {"symbols": ["BTCUSDT", "ETHUSDT"]}

        Returns: {
            "BTCUSDT": {"blacklisted": true, "reason": "HIGH_VOLATILITY"},
            "ETHUSDT": {"blacklisted": false}
        }
        """
        serializer = BlacklistCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        symbols = serializer.validated_data['symbols']
        results = {}

        for symbol in symbols:
            is_blacklisted = BlacklistedSymbol.is_blacklisted(symbol)

            if is_blacklisted:
                # Get blacklist details
                blacklist_entry = BlacklistedSymbol.objects.filter(
                    symbol=symbol,
                    active=True
                ).first()

                results[symbol] = {
                    'blacklisted': True,
                    'reason': blacklist_entry.reason if blacklist_entry else None,
                    'reason_display': blacklist_entry.get_reason_display() if blacklist_entry else None,
                    'notes': blacklist_entry.notes if blacklist_entry else None,
                    'blacklisted_at': blacklist_entry.blacklisted_at if blacklist_entry else None,
                    'blacklisted_until': blacklist_entry.blacklisted_until if blacklist_entry else None,
                }
            else:
                results[symbol] = {
                    'blacklisted': False
                }

        return Response(results)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def active(self, request):
        """
        Get list of currently active blacklisted symbols.

        GET /api/blacklist/active/

        Returns: {
            "blacklisted_symbols": ["BTCUSDT", "DOGEUSDT"],
            "count": 2
        }
        """
        blacklisted_symbols = BlacklistedSymbol.get_blacklisted_symbols()

        return Response({
            'blacklisted_symbols': blacklisted_symbols,
            'count': len(blacklisted_symbols)
        })

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a blacklist entry."""
        blacklist = self.get_object()
        blacklist.active = True
        blacklist.save()

        return Response({
            'message': f'{blacklist.symbol} has been activated in blacklist',
            'data': BlacklistedSymbolSerializer(blacklist).data
        })

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a blacklist entry."""
        blacklist = self.get_object()
        blacklist.active = False
        blacklist.save()

        return Response({
            'message': f'{blacklist.symbol} has been removed from blacklist',
            'data': BlacklistedSymbolSerializer(blacklist).data
        })

    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        """
        Extend blacklist duration.

        POST /api/blacklist/{id}/extend/
        Body: {"days": 7}
        """
        blacklist = self.get_object()
        days = request.data.get('days', 7)

        try:
            days = int(days)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid days value'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if blacklist.blacklisted_until:
            blacklist.blacklisted_until += timezone.timedelta(days=days)
        else:
            blacklist.blacklisted_until = timezone.now() + timezone.timedelta(days=days)

        blacklist.save()

        return Response({
            'message': f'{blacklist.symbol} blacklist extended by {days} days',
            'data': BlacklistedSymbolSerializer(blacklist).data
        })

    @action(detail=True, methods=['post'])
    def make_permanent(self, request, pk=None):
        """Remove expiration date (make permanent)."""
        blacklist = self.get_object()
        blacklist.blacklisted_until = None
        blacklist.save()

        return Response({
            'message': f'{blacklist.symbol} is now permanently blacklisted',
            'data': BlacklistedSymbolSerializer(blacklist).data
        })
