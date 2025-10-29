"""
Repository layer for database operations.
Implements repository pattern for data access abstraction following DRY principles.
"""
from typing import List, Optional, Dict, Any
from django.db.models import Q, Count, Avg, QuerySet
from django.utils import timezone
from datetime import timedelta
from .models import Symbol, Signal, UserSubscription


class BaseRepository:
    """
    Base repository with common database operations.
    Implements DRY principle for CRUD operations.
    """
    model = None

    def get_by_id(self, id: int) -> Optional[Any]:
        """Get object by ID."""
        try:
            return self.model.objects.get(id=id)
        except self.model.DoesNotExist:
            return None

    def get_all(self, **filters) -> QuerySet:
        """Get all objects with optional filters."""
        return self.model.objects.filter(**filters)

    def create(self, **data) -> Any:
        """Create new object."""
        return self.model.objects.create(**data)

    def update(self, id: int, **data) -> Optional[Any]:
        """Update object by ID."""
        obj = self.get_by_id(id)
        if obj:
            for key, value in data.items():
                setattr(obj, key, value)
            obj.save()
        return obj

    def delete(self, id: int) -> bool:
        """Delete object by ID."""
        obj = self.get_by_id(id)
        if obj:
            obj.delete()
            return True
        return False

    def bulk_create(self, objects: List[Any]) -> List[Any]:
        """Bulk create objects."""
        return self.model.objects.bulk_create(objects)

    def count(self, **filters) -> int:
        """Count objects with optional filters."""
        return self.model.objects.filter(**filters).count()


class SymbolRepository(BaseRepository):
    """
    Repository for Symbol model operations.
    """
    model = Symbol

    def get_by_symbol(self, symbol: str, exchange: str = 'BINANCE') -> Optional[Symbol]:
        """Get symbol by name and exchange."""
        try:
            return self.model.objects.get(symbol=symbol.upper(), exchange=exchange.upper())
        except self.model.DoesNotExist:
            return None

    def get_or_create_symbol(self, symbol: str, exchange: str = 'BINANCE') -> tuple:
        """Get or create symbol."""
        return self.model.objects.get_or_create(
            symbol=symbol.upper(),
            defaults={'exchange': exchange.upper(), 'active': True}
        )

    def get_active_symbols(self, exchange: Optional[str] = None) -> QuerySet:
        """Get all active symbols, optionally filtered by exchange."""
        filters = {'active': True}
        if exchange:
            filters['exchange'] = exchange.upper()
        return self.model.objects.filter(**filters)

    def get_symbols_with_signal_counts(self) -> QuerySet:
        """Get symbols with their active signal counts."""
        return self.model.objects.annotate(
            active_signals=Count('signals', filter=Q(signals__status='ACTIVE'))
        ).order_by('-active_signals')

    def deactivate_symbol(self, symbol_id: int) -> bool:
        """Deactivate a symbol."""
        return self.update(symbol_id, active=False) is not None

    def activate_symbol(self, symbol_id: int) -> bool:
        """Activate a symbol."""
        return self.update(symbol_id, active=True) is not None


class SignalRepository(BaseRepository):
    """
    Repository for Signal model operations with advanced filtering.
    """
    model = Signal

    def get_active_signals(self) -> QuerySet:
        """Get all active signals."""
        return self.model.objects.filter(status='ACTIVE').select_related('symbol', 'created_by')

    def get_signals_by_symbol(self, symbol_id: int, status: Optional[str] = None) -> QuerySet:
        """Get signals for a specific symbol."""
        filters = {'symbol_id': symbol_id}
        if status:
            filters['status'] = status
        return self.model.objects.filter(**filters).select_related('symbol')

    def get_signals_by_direction(self, direction: str, active_only: bool = True) -> QuerySet:
        """Get signals by direction (LONG/SHORT)."""
        filters = {'direction': direction.upper()}
        if active_only:
            filters['status'] = 'ACTIVE'
        return self.model.objects.filter(**filters).select_related('symbol')

    def get_signals_by_timeframe(self, timeframe: str, active_only: bool = True) -> QuerySet:
        """Get signals by timeframe."""
        filters = {'timeframe': timeframe}
        if active_only:
            filters['status'] = 'ACTIVE'
        return self.model.objects.filter(**filters).select_related('symbol')

    def get_high_confidence_signals(self, min_confidence: float = 0.7) -> QuerySet:
        """Get signals with confidence above threshold."""
        return self.model.objects.filter(
            confidence__gte=min_confidence,
            status='ACTIVE'
        ).select_related('symbol').order_by('-confidence')

    def get_signals_by_date_range(
        self,
        start_date: timezone.datetime,
        end_date: timezone.datetime
    ) -> QuerySet:
        """Get signals within date range."""
        return self.model.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).select_related('symbol', 'created_by')

    def get_recent_signals(self, hours: int = 24) -> QuerySet:
        """Get signals created in the last N hours."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.model.objects.filter(
            created_at__gte=cutoff_time
        ).select_related('symbol').order_by('-created_at')

    def get_expired_signals(self) -> QuerySet:
        """Get signals that should be marked as expired."""
        return self.model.objects.filter(
            expires_at__lte=timezone.now(),
            status='ACTIVE'
        )

    def expire_old_signals(self) -> int:
        """Mark expired signals as EXPIRED."""
        expired_signals = self.get_expired_signals()
        count = expired_signals.count()
        expired_signals.update(status='EXPIRED')
        return count

    def get_signals_by_user(self, user_id: int, status: Optional[str] = None) -> QuerySet:
        """Get signals created by a specific user."""
        filters = {'created_by_id': user_id}
        if status:
            filters['status'] = status
        return self.model.objects.filter(**filters).select_related('symbol')

    def filter_signals(self, filters: Dict[str, Any]) -> QuerySet:
        """
        Advanced signal filtering with multiple criteria.

        Args:
            filters: Dictionary with filter parameters
                - symbol: Symbol ID or name
                - direction: LONG/SHORT
                - status: Signal status
                - timeframe: Signal timeframe
                - min_confidence: Minimum confidence
                - max_confidence: Maximum confidence
                - created_after: Filter by creation date
                - created_before: Filter by creation date
        """
        queryset = self.model.objects.all()

        # Symbol filter
        if 'symbol' in filters:
            symbol = filters['symbol']
            if isinstance(symbol, int):
                queryset = queryset.filter(symbol_id=symbol)
            else:
                queryset = queryset.filter(symbol__symbol=symbol.upper())

        # Direction filter
        if 'direction' in filters:
            queryset = queryset.filter(direction=filters['direction'].upper())

        # Status filter
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'].upper())

        # Timeframe filter
        if 'timeframe' in filters:
            queryset = queryset.filter(timeframe=filters['timeframe'])

        # Confidence range
        if 'min_confidence' in filters:
            queryset = queryset.filter(confidence__gte=filters['min_confidence'])
        if 'max_confidence' in filters:
            queryset = queryset.filter(confidence__lte=filters['max_confidence'])

        # Date filters
        if 'created_after' in filters:
            queryset = queryset.filter(created_at__gte=filters['created_after'])
        if 'created_before' in filters:
            queryset = queryset.filter(created_at__lte=filters['created_before'])

        return queryset.select_related('symbol', 'created_by').order_by('-created_at')

    def get_signal_statistics(self) -> Dict[str, Any]:
        """Get overall signal statistics."""
        active_signals = self.get_active_signals()

        return {
            'total_signals': self.model.objects.count(),
            'active_signals': active_signals.count(),
            'long_signals': active_signals.filter(direction='LONG').count(),
            'short_signals': active_signals.filter(direction='SHORT').count(),
            'average_confidence': active_signals.aggregate(
                avg_confidence=Avg('confidence')
            )['avg_confidence'] or 0,
            'unique_symbols': active_signals.values('symbol').distinct().count(),
        }

    def bulk_update_status(self, signal_ids: List[int], status: str) -> int:
        """Bulk update signal statuses."""
        return self.model.objects.filter(id__in=signal_ids).update(status=status)


class UserSubscriptionRepository(BaseRepository):
    """
    Repository for UserSubscription model operations.
    """
    model = UserSubscription

    def get_by_user(self, user_id: int) -> Optional[UserSubscription]:
        """Get subscription by user ID."""
        try:
            return self.model.objects.get(user_id=user_id)
        except self.model.DoesNotExist:
            return None

    def get_or_create_for_user(self, user_id: int) -> tuple:
        """Get or create subscription for user."""
        return self.model.objects.get_or_create(
            user_id=user_id,
            defaults={'tier': 'free', 'status': 'active'}
        )

    def get_active_subscriptions(self, tier: Optional[str] = None) -> QuerySet:
        """Get all active subscriptions, optionally filtered by tier."""
        filters = {'status': 'active'}
        if tier:
            filters['tier'] = tier.lower()
        return self.model.objects.filter(**filters).select_related('user')

    def get_premium_users(self) -> QuerySet:
        """Get all users with premium (pro/premium) subscriptions."""
        return self.model.objects.filter(
            tier__in=['pro', 'premium'],
            status='active'
        ).select_related('user')

    def get_expired_subscriptions(self) -> QuerySet:
        """Get subscriptions that have expired."""
        return self.model.objects.filter(
            expires_at__lte=timezone.now(),
            status='active'
        )

    def expire_old_subscriptions(self) -> int:
        """Mark expired subscriptions as EXPIRED."""
        expired_subs = self.get_expired_subscriptions()
        count = expired_subs.count()
        expired_subs.update(status='expired')
        return count

    def upgrade_subscription(
        self,
        user_id: int,
        new_tier: str,
        stripe_customer_id: str,
        stripe_subscription_id: str,
        expires_at: Optional[timezone.datetime] = None
    ) -> Optional[UserSubscription]:
        """Upgrade user subscription to a new tier."""
        subscription = self.get_by_user(user_id)
        if subscription:
            subscription.tier = new_tier
            subscription.status = 'active'
            subscription.stripe_customer_id = stripe_customer_id
            subscription.stripe_subscription_id = stripe_subscription_id
            subscription.expires_at = expires_at
            subscription.save()
        return subscription

    def cancel_subscription(self, user_id: int) -> bool:
        """Cancel user subscription."""
        subscription = self.get_by_user(user_id)
        if subscription:
            subscription.status = 'cancelled'
            subscription.save()
            return True
        return False

    def get_subscription_statistics(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        return {
            'total_subscriptions': self.model.objects.count(),
            'active_subscriptions': self.model.objects.filter(status='active').count(),
            'free_users': self.model.objects.filter(tier='free').count(),
            'pro_users': self.model.objects.filter(tier='pro', status='active').count(),
            'premium_users': self.model.objects.filter(tier='premium', status='active').count(),
        }

    def get_by_stripe_customer_id(self, stripe_customer_id: str) -> Optional[UserSubscription]:
        """Get subscription by Stripe customer ID."""
        try:
            return self.model.objects.get(stripe_customer_id=stripe_customer_id)
        except self.model.DoesNotExist:
            return None


# Repository instances for easy access
symbol_repository = SymbolRepository()
signal_repository = SignalRepository()
subscription_repository = UserSubscriptionRepository()
