"""
API Views for signals using ViewSets.
Implements clean architecture with separated presentation layer.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .models import Symbol, Signal, UserSubscription
from .serializers import (
    SymbolSerializer,
    SymbolListSerializer,
    SignalSerializer,
    SignalListSerializer,
    UserSubscriptionSerializer,
    SignalStatusUpdateSerializer
)
from .services import (
    SignalScoringService,
    SignalManagementService,
    SubscriptionService,
    AnalyticsService
)
from .repositories import signal_repository, symbol_repository, subscription_repository


class SymbolViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Symbol model.
    Read-only access for all users, admin can create via admin panel.
    """
    queryset = Symbol.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['symbol', 'exchange']
    ordering_fields = ['symbol', 'created_at', 'active']
    ordering = ['symbol']

    def get_serializer_class(self):
        """Use different serializer for list and detail views."""
        if self.action == 'list':
            return SymbolListSerializer
        return SymbolSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = Symbol.objects.all()

        # Filter by active status
        active = self.request.query_params.get('active', None)
        if active is not None:
            queryset = queryset.filter(active=active.lower() == 'true')

        # Filter by exchange
        exchange = self.request.query_params.get('exchange', None)
        if exchange:
            queryset = queryset.filter(exchange=exchange.upper())

        return queryset

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active symbols."""
        symbols = symbol_repository.get_active_symbols()
        serializer = SymbolListSerializer(symbols, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def with_signals(self, request):
        """Get symbols with their signal counts."""
        symbols = symbol_repository.get_symbols_with_signal_counts()
        serializer = SymbolSerializer(symbols, many=True)
        return Response(serializer.data)


class SignalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Signal model.
    Read-only for regular users, admins can create signals.
    """
    queryset = Signal.objects.select_related('symbol', 'created_by').all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['direction', 'status', 'timeframe', 'symbol', 'market_type']
    search_fields = ['symbol__symbol', 'description', 'source']
    ordering_fields = ['created_at', 'confidence', 'entry']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Use different serializer for list and detail views."""
        if self.action == 'list':
            return SignalListSerializer
        return SignalSerializer

    def get_queryset(self):
        """
        Filter queryset based on user subscription and query parameters.
        """
        queryset = Signal.objects.select_related('symbol', 'created_by').all()

        # Get user subscription to determine access level
        if self.request.user.is_authenticated:
            subscription = subscription_repository.get_by_user(self.request.user.id)

            # Free users only see active signals, limited count
            if not subscription or subscription.tier == 'free':
                queryset = queryset.filter(status='ACTIVE')

        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        # Filter by direction
        direction = self.request.query_params.get('direction', None)
        if direction:
            queryset = queryset.filter(direction=direction.upper())

        # Filter by timeframe
        timeframe = self.request.query_params.get('timeframe', None)
        if timeframe:
            queryset = queryset.filter(timeframe=timeframe)

        # Filter by minimum confidence
        min_confidence = self.request.query_params.get('min_confidence', None)
        if min_confidence:
            try:
                queryset = queryset.filter(confidence__gte=float(min_confidence))
            except ValueError:
                pass

        # Filter by symbol
        symbol = self.request.query_params.get('symbol', None)
        if symbol:
            queryset = queryset.filter(symbol__symbol=symbol.upper())

        return queryset

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active signals."""
        if request.user.is_authenticated:
            signals = SignalManagementService.get_active_signals_for_user(request.user)
        else:
            signals = list(signal_repository.get_active_signals()[:5])

        serializer = SignalListSerializer(signals, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def high_confidence(self, request):
        """Get high confidence signals (>= 0.7)."""
        min_conf = float(request.query_params.get('min', 0.7))
        signals = signal_repository.get_high_confidence_signals(min_confidence=min_conf)

        # Limit for non-premium users
        if request.user.is_authenticated:
            subscription = subscription_repository.get_by_user(request.user.id)
            if not subscription or subscription.tier == 'free':
                signals = signals[:5]

        serializer = SignalListSerializer(signals, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent signals from last N hours."""
        hours = int(request.query_params.get('hours', 24))
        signals = signal_repository.get_recent_signals(hours=hours)

        # Limit for non-premium users
        if request.user.is_authenticated:
            subscription = subscription_repository.get_by_user(request.user.id)
            if not subscription or subscription.tier == 'free':
                signals = signals[:10]

        serializer = SignalListSerializer(signals, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def ranked(self, request):
        """Get signals ranked by score."""
        active_signals = list(signal_repository.get_active_signals()[:20])
        ranked = SignalScoringService.rank_signals(active_signals)

        # Serialize with scores
        data = []
        for item in ranked:
            signal_data = SignalSerializer(item['signal']).data
            signal_data['score'] = item['score']
            signal_data['rank'] = item['rank']
            data.append(signal_data)

        return Response(data)

    @action(detail=True, methods=['get'])
    def score(self, request, pk=None):
        """Get signal score."""
        signal = self.get_object()
        score = SignalScoringService.calculate_signal_score(signal)

        return Response({
            'signal_id': signal.id,
            'score': score,
            'confidence': signal.confidence,
            'risk_reward_ratio': signal.risk_reward_ratio
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def create_signal(self, request):
        """
        Create a new signal (admin only).
        """
        result = SignalManagementService.create_signal(
            data=request.data,
            user=request.user
        )

        if not result['success']:
            return Response(
                {'error': result.get('error', result.get('errors'))},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SignalSerializer(result['signal'])
        return Response({
            'signal': serializer.data,
            'score': result['score']
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_update_status(self, request):
        """
        Bulk update signal statuses (admin only).
        """
        serializer = SignalStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        signal_ids = serializer.validated_data['signal_ids']
        new_status = serializer.validated_data['status']

        count = signal_repository.bulk_update_status(signal_ids, new_status)

        return Response({
            'updated': count,
            'status': new_status
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """Update signal status (admin only)."""
        signal = self.get_object()
        new_status = request.data.get('status')

        if not new_status:
            return Response(
                {'error': 'Status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = SignalManagementService.update_signal_status(signal.id, new_status)

        if not result['success']:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SignalSerializer(result['signal'])
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get signal statistics."""
        stats = signal_repository.get_signal_statistics()
        return Response(stats)

    @action(detail=False, methods=['get'])
    def by_symbol(self, request):
        """Get signals for a specific symbol."""
        symbol_name = request.query_params.get('symbol')
        if not symbol_name:
            return Response(
                {'error': 'Symbol parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        symbol = symbol_repository.get_by_symbol(symbol_name)
        if not symbol:
            return Response(
                {'error': 'Symbol not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        signals = signal_repository.get_signals_by_symbol(symbol.id)
        serializer = SignalListSerializer(signals, many=True)
        return Response(serializer.data)


class UserSubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserSubscription model.
    Users can only view/update their own subscription.
    """
    queryset = UserSubscription.objects.select_related('user').all()
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Users can only see their own subscription."""
        if self.request.user.is_staff:
            return UserSubscription.objects.all()
        return UserSubscription.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's subscription."""
        subscription = subscription_repository.get_by_user(request.user.id)

        if not subscription:
            # Create free subscription if doesn't exist
            subscription = SubscriptionService.create_free_subscription(request.user)

        serializer = UserSubscriptionSerializer(subscription)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def features(self, request):
        """Get features for current user's subscription tier."""
        subscription = subscription_repository.get_by_user(request.user.id)

        if not subscription:
            tier = 'free'
        else:
            tier = subscription.tier

        features = SubscriptionService.get_subscription_features(tier)
        return Response({
            'tier': tier,
            'features': features
        })

    @action(detail=False, methods=['post'])
    def upgrade(self, request):
        """Upgrade subscription to paid tier."""
        tier = request.data.get('tier')
        stripe_customer_id = request.data.get('stripe_customer_id')
        stripe_subscription_id = request.data.get('stripe_subscription_id')

        if not all([tier, stripe_customer_id, stripe_subscription_id]):
            return Response(
                {'error': 'tier, stripe_customer_id, and stripe_subscription_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = SubscriptionService.upgrade_to_paid(
            user=request.user,
            tier=tier,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id
        )

        if not result['success']:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserSubscriptionSerializer(result['subscription'])
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Cancel current subscription."""
        result = SubscriptionService.cancel_subscription(request.user)

        if not result['success']:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({'message': result['message']})

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def statistics(self, request):
        """Get subscription statistics (admin only)."""
        stats = subscription_repository.get_subscription_statistics()
        return Response(stats)


class AnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for analytics and statistics.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard statistics."""
        stats = AnalyticsService.get_dashboard_stats()
        return Response(stats)

    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Get signal performance metrics."""
        timeframe = request.query_params.get('timeframe', '24h')
        metrics = AnalyticsService.get_signal_performance_metrics(timeframe)
        return Response(metrics)

    @action(detail=False, methods=['get'])
    def top_symbols(self, request):
        """Get top symbols by signal count."""
        limit = int(request.query_params.get('limit', 10))
        top_symbols = AnalyticsService.get_top_symbols(limit=limit)
        return Response(top_symbols)
