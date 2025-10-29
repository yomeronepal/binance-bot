"""
Business logic services for signal processing.
Implements domain logic separate from data and presentation layers.
"""
from typing import Dict, Any, List, Optional
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from ..models import Symbol, Signal, UserSubscription
from ..repositories import (
    symbol_repository,
    signal_repository,
    subscription_repository
)


class SignalScoringService:
    """
    Service for scoring and evaluating signals.
    """

    @staticmethod
    def calculate_signal_score(signal: Signal) -> float:
        """
        Calculate comprehensive signal score (0-100).

        Factors:
        - Confidence level (40%)
        - Risk/reward ratio (30%)
        - Signal freshness (20%)
        - Source reliability (10%)
        """
        score = 0.0

        # Confidence score (0-40 points)
        confidence_score = signal.confidence * 40

        # Risk/reward score (0-30 points)
        rr_ratio = signal.risk_reward_ratio
        if rr_ratio:
            # Ideal RR is 2:1 or better
            if rr_ratio >= 2:
                rr_score = 30
            elif rr_ratio >= 1.5:
                rr_score = 25
            elif rr_ratio >= 1:
                rr_score = 20
            else:
                rr_score = 10
        else:
            rr_score = 0

        # Freshness score (0-20 points)
        age_hours = (timezone.now() - signal.created_at).total_seconds() / 3600
        if age_hours < 1:
            freshness_score = 20
        elif age_hours < 4:
            freshness_score = 15
        elif age_hours < 12:
            freshness_score = 10
        elif age_hours < 24:
            freshness_score = 5
        else:
            freshness_score = 0

        # Source reliability (0-10 points)
        # Can be enhanced with historical performance data
        source_score = 10 if signal.source else 5

        score = confidence_score + rr_score + freshness_score + source_score
        return round(score, 2)

    @staticmethod
    def rank_signals(signals: List[Signal]) -> List[Dict[str, Any]]:
        """
        Rank signals by score and return sorted list with scores.
        """
        scored_signals = []
        for signal in signals:
            score = SignalScoringService.calculate_signal_score(signal)
            scored_signals.append({
                'signal': signal,
                'score': score,
                'rank': None  # Will be assigned after sorting
            })

        # Sort by score descending
        scored_signals.sort(key=lambda x: x['score'], reverse=True)

        # Assign ranks
        for idx, item in enumerate(scored_signals, start=1):
            item['rank'] = idx

        return scored_signals


class SignalValidationService:
    """
    Service for validating signal data and business rules.
    """

    @staticmethod
    def validate_price_levels(
        direction: str,
        entry: Decimal,
        sl: Decimal,
        tp: Decimal
    ) -> Dict[str, Any]:
        """
        Validate price levels make sense for the direction.
        """
        errors = []

        if direction == 'LONG':
            if sl >= entry:
                errors.append("Stop loss must be below entry for LONG signals")
            if tp <= entry:
                errors.append("Take profit must be above entry for LONG signals")
        else:  # SHORT
            if sl <= entry:
                errors.append("Stop loss must be above entry for SHORT signals")
            if tp >= entry:
                errors.append("Take profit must be below entry for SHORT signals")

        # Check risk/reward ratio
        if direction == 'LONG':
            risk = float(entry - sl)
            reward = float(tp - entry)
        else:
            risk = float(sl - entry)
            reward = float(entry - tp)

        rr_ratio = reward / risk if risk > 0 else 0

        if rr_ratio < 1:
            errors.append(f"Risk/reward ratio ({rr_ratio:.2f}) is less than 1:1")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'risk_reward_ratio': round(rr_ratio, 2)
        }

    @staticmethod
    def validate_user_can_create_signal(user) -> Dict[str, Any]:
        """
        Check if user can create more signals based on their subscription.
        """
        subscription = subscription_repository.get_by_user(user.id)

        if not subscription:
            return {'allowed': False, 'reason': 'No subscription found'}

        if not subscription.is_active:
            return {'allowed': False, 'reason': 'Subscription is not active'}

        # Check daily limit
        signal_limit = subscription.get_signal_limit()

        if signal_limit is None:  # Unlimited
            return {'allowed': True, 'remaining': None}

        # Count signals created today
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        signals_today = signal_repository.get_signals_by_user(
            user.id
        ).filter(created_at__gte=today_start).count()

        if signals_today >= signal_limit:
            return {
                'allowed': False,
                'reason': f'Daily limit of {signal_limit} signals reached',
                'used': signals_today,
                'limit': signal_limit
            }

        return {
            'allowed': True,
            'remaining': signal_limit - signals_today,
            'limit': signal_limit
        }


class SignalManagementService:
    """
    Service for managing signal lifecycle.
    """

    @staticmethod
    def create_signal(data: Dict[str, Any], user) -> Dict[str, Any]:
        """
        Create a new signal with validation.
        """
        # Validate user can create signals
        validation = SignalValidationService.validate_user_can_create_signal(user)
        if not validation['allowed']:
            return {
                'success': False,
                'error': validation['reason']
            }

        # Validate price levels
        price_validation = SignalValidationService.validate_price_levels(
            direction=data['direction'],
            entry=data['entry'],
            sl=data['sl'],
            tp=data['tp']
        )

        if not price_validation['valid']:
            return {
                'success': False,
                'errors': price_validation['errors']
            }

        # Get or create symbol
        symbol, _ = symbol_repository.get_or_create_symbol(
            data.get('symbol_name', ''),
            data.get('exchange', 'BINANCE')
        )

        # Create signal
        signal_data = {
            'symbol': symbol,
            'direction': data['direction'],
            'timeframe': data.get('timeframe', '1h'),
            'entry': data['entry'],
            'sl': data['sl'],
            'tp': data['tp'],
            'confidence': data.get('confidence', 0.5),
            'source': data.get('source', ''),
            'description': data.get('description', ''),
            'meta': data.get('meta', {}),
            'created_by': user
        }

        # Set expiration if provided
        if 'expires_hours' in data:
            signal_data['expires_at'] = timezone.now() + timedelta(hours=data['expires_hours'])

        signal = signal_repository.create(**signal_data)

        return {
            'success': True,
            'signal': signal,
            'score': SignalScoringService.calculate_signal_score(signal)
        }

    @staticmethod
    def update_signal_status(signal_id: int, new_status: str) -> Dict[str, Any]:
        """
        Update signal status with validation.
        """
        signal = signal_repository.get_by_id(signal_id)

        if not signal:
            return {'success': False, 'error': 'Signal not found'}

        # Validate status transition
        valid_transitions = {
            'ACTIVE': ['EXECUTED', 'EXPIRED', 'CANCELLED'],
            'EXECUTED': [],
            'EXPIRED': [],
            'CANCELLED': []
        }

        if new_status not in valid_transitions.get(signal.status, []):
            return {
                'success': False,
                'error': f'Cannot transition from {signal.status} to {new_status}'
            }

        signal.status = new_status
        signal.save()

        return {'success': True, 'signal': signal}

    @staticmethod
    def expire_old_signals() -> int:
        """
        Mark expired signals as EXPIRED.
        """
        return signal_repository.expire_old_signals()

    @staticmethod
    def get_active_signals_for_user(user) -> List[Signal]:
        """
        Get active signals accessible to user based on subscription.
        """
        subscription = subscription_repository.get_by_user(user.id)

        signals = signal_repository.get_active_signals()

        # Free users see limited signals
        if not subscription or subscription.tier == 'free':
            signals = signals[:5]

        return list(signals)


class SubscriptionService:
    """
    Service for managing user subscriptions.
    """

    @staticmethod
    def create_free_subscription(user) -> UserSubscription:
        """
        Create free subscription for new user.
        """
        subscription, created = subscription_repository.get_or_create_for_user(user.id)
        return subscription

    @staticmethod
    def upgrade_to_paid(
        user,
        tier: str,
        stripe_customer_id: str,
        stripe_subscription_id: str
    ) -> Dict[str, Any]:
        """
        Upgrade user to paid subscription.
        """
        if tier not in ['pro', 'premium']:
            return {'success': False, 'error': 'Invalid tier'}

        # Set expiration to 30 days from now
        expires_at = timezone.now() + timedelta(days=30)

        subscription = subscription_repository.upgrade_subscription(
            user_id=user.id,
            new_tier=tier,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            expires_at=expires_at
        )

        if not subscription:
            return {'success': False, 'error': 'Failed to upgrade subscription'}

        return {
            'success': True,
            'subscription': subscription,
            'expires_at': expires_at
        }

    @staticmethod
    def cancel_subscription(user) -> Dict[str, Any]:
        """
        Cancel user subscription.
        """
        success = subscription_repository.cancel_subscription(user.id)

        if not success:
            return {'success': False, 'error': 'Subscription not found'}

        return {'success': True, 'message': 'Subscription cancelled'}

    @staticmethod
    def check_and_expire_subscriptions() -> int:
        """
        Check and expire old subscriptions.
        """
        return subscription_repository.expire_old_subscriptions()

    @staticmethod
    def get_subscription_features(tier: str) -> Dict[str, Any]:
        """
        Get features available for a subscription tier.
        """
        features = {
            'free': {
                'signals_per_day': 5,
                'advanced_analytics': False,
                'api_access': False,
                'custom_alerts': False,
                'priority_support': False
            },
            'pro': {
                'signals_per_day': 50,
                'advanced_analytics': True,
                'api_access': True,
                'custom_alerts': True,
                'priority_support': False
            },
            'premium': {
                'signals_per_day': None,  # Unlimited
                'advanced_analytics': True,
                'api_access': True,
                'custom_alerts': True,
                'priority_support': True
            }
        }

        return features.get(tier, features['free'])


class AnalyticsService:
    """
    Service for analytics and statistics.
    """

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """
        Get dashboard statistics.
        """
        signal_stats = signal_repository.get_signal_statistics()
        subscription_stats = subscription_repository.get_subscription_statistics()

        return {
            'signals': signal_stats,
            'subscriptions': subscription_stats,
            'top_symbols': AnalyticsService.get_top_symbols(limit=10)
        }

    @staticmethod
    def get_top_symbols(limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top symbols by active signal count.
        """
        symbols = symbol_repository.get_symbols_with_signal_counts()[:limit]

        return [
            {
                'symbol': symbol.symbol,
                'exchange': symbol.exchange,
                'active_signals': symbol.active_signals
            }
            for symbol in symbols
        ]

    @staticmethod
    def get_signal_performance_metrics(timeframe: str = '24h') -> Dict[str, Any]:
        """
        Get signal performance metrics for a timeframe.
        """
        hours_map = {'1h': 1, '24h': 24, '7d': 168, '30d': 720}
        hours = hours_map.get(timeframe, 24)

        recent_signals = signal_repository.get_recent_signals(hours=hours)

        total = recent_signals.count()
        if total == 0:
            return {
                'total_signals': 0,
                'average_confidence': 0,
                'long_percentage': 0,
                'short_percentage': 0
            }

        long_count = recent_signals.filter(direction='LONG').count()
        short_count = recent_signals.filter(direction='SHORT').count()

        avg_confidence = sum(s.confidence for s in recent_signals) / total

        return {
            'total_signals': total,
            'average_confidence': round(avg_confidence, 2),
            'long_signals': long_count,
            'short_signals': short_count,
            'long_percentage': round((long_count / total) * 100, 1),
            'short_percentage': round((short_count / total) * 100, 1)
        }
