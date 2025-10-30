"""
Celery Tasks for Strategy Optimization
Auto-optimization, continuous learning, and performance monitoring
"""
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
import logging

from signals.services.optimizer_service import (
    StrategyOptimizer,
    TradeCounterService
)
from signals.models_optimization import OptimizationRun, StrategyConfigHistory

logger = logging.getLogger(__name__)


@shared_task(name='signals.auto_optimize_strategy')
def auto_optimize_strategy(volatility_level='ALL', lookback_days=30, trigger='SCHEDULED'):
    """
    Main auto-optimization task.
    Runs optimization cycle for specified volatility level.

    Args:
        volatility_level: HIGH, MEDIUM, LOW, or ALL
        lookback_days: Days of historical data to use for backtesting
        trigger: What triggered this optimization

    Returns:
        dict with optimization results
    """
    try:
        logger.info(f"🤖 Starting auto-optimization task")
        logger.info(f"   Volatility: {volatility_level}")
        logger.info(f"   Lookback: {lookback_days} days")
        logger.info(f"   Trigger: {trigger}")

        # Get system user for optimization
        user = User.objects.filter(is_staff=True).first()

        # Run optimization
        optimizer = StrategyOptimizer(
            volatility_level=volatility_level,
            lookback_days=lookback_days,
            user=user
        )

        opt_run = optimizer.run_optimization_cycle(trigger=trigger)

        # Reset trade counter if successful
        if opt_run.status == 'COMPLETED':
            TradeCounterService.reset_counter(volatility_level)

        # Send notification
        if opt_run.improvement_found:
            send_optimization_notification.delay(opt_run.id)

        result = {
            'status': 'success',
            'run_id': opt_run.run_id,
            'improvement_found': opt_run.improvement_found,
            'improvement_percentage': float(opt_run.improvement_percentage or 0),
            'duration_seconds': opt_run.duration_seconds,
            'timestamp': timezone.now().isoformat()
        }

        logger.info(f"✅ Auto-optimization completed: {opt_run.run_id}")
        return result

    except Exception as e:
        logger.error(f"❌ Auto-optimization failed: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='signals.check_trade_threshold')
def check_trade_threshold():
    """
    Check if trade count threshold has been reached for any volatility level.
    If yes, trigger optimization.

    This task runs periodically (e.g., every hour) to check counters.
    """
    try:
        logger.info("🔍 Checking trade thresholds...")

        status = TradeCounterService.get_counter_status()

        for counter in status:
            vol_level = counter['volatility_level']
            count = counter['count']
            threshold = counter['threshold']
            percentage = counter['percentage']

            logger.info(f"   {vol_level}: {count}/{threshold} ({percentage:.1f}%)")

            if percentage >= 100:
                logger.info(f"🎯 Threshold reached for {vol_level} - triggering optimization")

                # Trigger optimization asynchronously
                auto_optimize_strategy.delay(
                    volatility_level=vol_level,
                    lookback_days=30,
                    trigger='TRADE_COUNT'
                )

        return {
            'status': 'success',
            'counters_checked': len(status),
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Trade threshold check failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='signals.scheduled_optimization')
def scheduled_optimization():
    """
    Run scheduled optimization for all volatility levels.
    Runs weekly to keep strategies fresh even if trade threshold isn't reached.
    """
    try:
        logger.info("📅 Running scheduled optimization for all volatility levels")

        volatility_levels = ['LOW', 'MEDIUM', 'HIGH']

        for vol_level in volatility_levels:
            logger.info(f"   Scheduling optimization for {vol_level}...")

            auto_optimize_strategy.delay(
                volatility_level=vol_level,
                lookback_days=30,
                trigger='SCHEDULED'
            )

        return {
            'status': 'success',
            'levels_scheduled': len(volatility_levels),
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Scheduled optimization failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='signals.send_optimization_notification')
def send_optimization_notification(optimization_run_id):
    """
    Send notification about optimization results.

    Args:
        optimization_run_id: ID of OptimizationRun to notify about
    """
    try:
        opt_run = OptimizationRun.objects.get(id=optimization_run_id)

        if opt_run.notification_sent:
            logger.info(f"Notification already sent for {opt_run.run_id}")
            return {'status': 'skipped', 'reason': 'already_sent'}

        logger.info(f"📧 Sending optimization notification for {opt_run.run_id}")

        # Build notification message
        message = _build_notification_message(opt_run)

        # Send via multiple channels
        notifications_sent = []

        # 1. Log notification
        logger.info(f"\n{'='*70}\n{message}\n{'='*70}")
        notifications_sent.append('log')

        # 2. TODO: Send Discord notification
        # if settings.DISCORD_WEBHOOK_URL:
        #     send_discord_notification(message)
        #     notifications_sent.append('discord')

        # 3. TODO: Send email notification
        # if settings.OPTIMIZATION_EMAIL:
        #     send_email_notification(message)
        #     notifications_sent.append('email')

        # Mark as sent
        opt_run.notification_sent = True
        opt_run.notification_sent_at = timezone.now()
        opt_run.save()

        return {
            'status': 'success',
            'run_id': opt_run.run_id,
            'channels': notifications_sent,
            'timestamp': timezone.now().isoformat()
        }

    except OptimizationRun.DoesNotExist:
        logger.error(f"OptimizationRun {optimization_run_id} not found")
        return {'status': 'error', 'error': 'run_not_found'}

    except Exception as e:
        logger.error(f"❌ Notification failed: {str(e)}")
        return {'status': 'error', 'error': str(e)}


def _build_notification_message(opt_run):
    """Build formatted notification message"""
    message_parts = [
        "🤖 STRATEGY OPTIMIZATION COMPLETE",
        "",
        f"Run ID: {opt_run.run_id}",
        f"Trigger: {opt_run.get_trigger_display()}",
        f"Volatility Level: {opt_run.volatility_level}",
        f"Duration: {opt_run.duration_seconds}s",
        "",
    ]

    if opt_run.improvement_found:
        message_parts.extend([
            "✅ IMPROVEMENT FOUND - NEW CONFIG APPLIED",
            "",
            f"Baseline Score: {opt_run.baseline_score:.2f}",
            f"New Score: {opt_run.best_score:.2f}",
            f"Improvement: +{opt_run.improvement_percentage:.2f}%",
            "",
        ])

        if opt_run.winning_config:
            config = opt_run.winning_config
            message_parts.extend([
                "New Configuration:",
                f"  Name: {config.config_name} v{config.version}",
                f"  Win Rate: {config.get_metric('win_rate', 0):.1f}%",
                f"  Profit Factor: {config.get_metric('profit_factor', 0):.2f}",
                f"  Sharpe Ratio: {config.get_metric('sharpe_ratio', 0):.2f}",
                f"  ROI: {config.get_metric('roi', 0):.2f}%",
                "",
                "Parameters:",
            ])

            for key, value in config.parameters.items():
                message_parts.append(f"  {key}: {value}")
    else:
        message_parts.extend([
            "⏸️ NO IMPROVEMENT FOUND - KEEPING CURRENT CONFIG",
            "",
            f"Baseline Score: {opt_run.baseline_score:.2f}",
            f"Best Candidate Score: {opt_run.best_score:.2f}",
            f"Improvement: {opt_run.improvement_percentage:+.2f}% (below 5% threshold)",
        ])

    message_parts.extend([
        "",
        f"Candidates Tested: {opt_run.candidates_tested}",
        f"Trades Analyzed: {opt_run.trades_analyzed}",
        f"Lookback Period: {opt_run.lookback_days} days",
    ])

    return "\n".join(message_parts)


@shared_task(name='signals.monitor_config_performance')
def monitor_config_performance():
    """
    Monitor active configuration performance.
    Trigger optimization if performance drops significantly.
    """
    try:
        logger.info("📊 Monitoring active configuration performance...")

        active_configs = StrategyConfigHistory.objects.filter(status='ACTIVE')

        for config in active_configs:
            logger.info(f"   Checking {config.config_name} ({config.volatility_level})")

            # Get recent trades for this config
            # TODO: Implement performance monitoring logic
            # - Calculate recent win rate
            # - Compare with config baseline
            # - Trigger optimization if drop > 15%

        return {
            'status': 'success',
            'configs_monitored': active_configs.count(),
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Performance monitoring failed: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='signals.cleanup_old_optimization_runs')
def cleanup_old_optimization_runs(days=90):
    """
    Clean up old optimization runs to prevent database bloat.
    Keeps runs from last N days.

    Args:
        days: Number of days to keep (default 90)
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        deleted_count = OptimizationRun.objects.filter(
            started_at__lt=cutoff_date,
            improvement_found=False  # Keep successful runs
        ).delete()[0]

        logger.info(f"🗑️ Cleaned up {deleted_count} old optimization runs")

        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {str(e)}")
        return {'status': 'error', 'error': str(e)}
