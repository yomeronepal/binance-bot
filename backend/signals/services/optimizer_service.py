"""
Strategy Optimizer Service
Auto-learns from trades and optimizes strategy parameters
"""
from django.utils import timezone
from django.db.models import Avg, Sum, Count
from datetime import timedelta
from decimal import Decimal
import logging
import json
import uuid

from signals.models_backtest import BacktestRun, BacktestTrade
from signals.models_optimization import (
    StrategyConfigHistory,
    OptimizationRun,
    TradeCounter
)

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """
    Continuous learning and auto-optimization engine.

    Workflow:
    1. Triggered after N trades or on schedule
    2. Runs backtest with current config (baseline)
    3. Generates candidate configs with parameter variations
    4. Runs backtests for all candidates
    5. Compares results using fitness scoring
    6. Applies best config if it improves performance
    7. Logs results and sends notifications
    """

    def __init__(self, volatility_level='ALL', lookback_days=30, user=None):
        self.volatility_level = volatility_level
        self.lookback_days = lookback_days
        self.user = user
        self.run_id = f"opt_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def run_optimization_cycle(self, trigger='SCHEDULED'):
        """
        Main optimization cycle.

        Args:
            trigger: What triggered this optimization (TRADE_COUNT, SCHEDULED, MANUAL, etc.)

        Returns:
            OptimizationRun object with results
        """
        logger.info(f"🚀 Starting optimization cycle: {self.run_id}")
        logger.info(f"   Trigger: {trigger}")
        logger.info(f"   Volatility: {self.volatility_level}")
        logger.info(f"   Lookback: {self.lookback_days} days")

        # Create optimization run record
        opt_run = OptimizationRun.objects.create(
            run_id=self.run_id,
            trigger=trigger,
            volatility_level=self.volatility_level,
            lookback_days=self.lookback_days,
            status='RUNNING'
        )

        try:
            # Step 1: Get current baseline config
            baseline_config = self._get_baseline_config()
            if baseline_config:
                opt_run.baseline_config = baseline_config
                opt_run.baseline_score = baseline_config.calculate_fitness_score()
                opt_run.save()

                logger.info(f"📊 Baseline config: {baseline_config.config_name}")
                logger.info(f"   Baseline score: {opt_run.baseline_score}")

            # Step 2: Evaluate baseline performance
            baseline_metrics = self._evaluate_current_config(baseline_config)
            logger.info(f"   Baseline metrics: Win rate={baseline_metrics.get('win_rate', 0):.1f}%, "
                       f"Profit factor={baseline_metrics.get('profit_factor', 0):.2f}")

            # Step 3: Generate candidate configurations
            candidates = self._generate_candidate_configs(baseline_config)
            logger.info(f"🧪 Generated {len(candidates)} candidate configurations")

            opt_run.candidates_tested = len(candidates)
            opt_run.save()

            # Step 4: Test each candidate
            results = []
            for idx, candidate_params in enumerate(candidates, 1):
                logger.info(f"   Testing candidate {idx}/{len(candidates)}...")

                metrics = self._run_backtest(
                    symbols=self._get_symbols_for_volatility(),
                    config=candidate_params,
                    lookback_days=self.lookback_days
                )

                if metrics:
                    # Create config history record
                    candidate_config = StrategyConfigHistory.objects.create(
                        config_name=f"{self.volatility_level}_optimized",
                        volatility_level=self.volatility_level,
                        version=self._get_next_version(),
                        parameters=candidate_params,
                        metrics=metrics,
                        status='TESTING',
                        baseline_config=baseline_config,
                        created_by=self.user
                    )

                    fitness_score = candidate_config.calculate_fitness_score()
                    results.append({
                        'config': candidate_config,
                        'params': candidate_params,
                        'metrics': metrics,
                        'fitness_score': fitness_score
                    })

                    logger.info(f"      Fitness score: {fitness_score:.2f}")

            # Step 5: Find best performing candidate
            if results:
                best_result = max(results, key=lambda x: x['fitness_score'])
                best_config = best_result['config']
                best_score = best_result['fitness_score']

                opt_run.best_score = best_score
                opt_run.save()

                logger.info(f"🏆 Best candidate score: {best_score:.2f}")

                # Step 6: Compare with baseline and decide
                baseline_score = opt_run.baseline_score or 0
                improvement = ((best_score - baseline_score) / baseline_score * 100) if baseline_score > 0 else 0

                logger.info(f"📈 Improvement: {improvement:+.2f}%")

                # Apply if improvement meets threshold (>5%)
                if improvement >= 5.0:
                    logger.info("✅ Improvement threshold met - applying new config")

                    best_config.improved = True
                    best_config.improvement_percentage = Decimal(improvement)
                    best_config.mark_as_active()

                    opt_run.improvement_found = True
                    opt_run.winning_config = best_config
                    opt_run.improvement_percentage = Decimal(improvement)

                    # Log detailed results
                    opt_run.results = {
                        'baseline': {
                            'params': baseline_config.parameters if baseline_config else {},
                            'metrics': baseline_metrics,
                            'score': float(baseline_score)
                        },
                        'best_candidate': {
                            'params': best_result['params'],
                            'metrics': best_result['metrics'],
                            'score': float(best_score)
                        },
                        'improvement_pct': float(improvement),
                        'all_candidates': [
                            {
                                'params': r['params'],
                                'score': float(r['fitness_score'])
                            }
                            for r in results
                        ]
                    }
                else:
                    logger.info("⏸️ Improvement below threshold - keeping current config")
                    best_config.status = 'ARCHIVED'
                    best_config.save()

            # Step 7: Mark run as completed
            opt_run.mark_completed(winning_config=best_config if improvement >= 5.0 else None)

            logger.info(f"✅ Optimization cycle completed: {self.run_id}")
            logger.info(f"   Duration: {opt_run.duration_seconds}s")
            logger.info(f"   Improvement found: {opt_run.improvement_found}")

            return opt_run

        except Exception as e:
            logger.error(f"❌ Optimization cycle failed: {str(e)}", exc_info=True)
            opt_run.status = 'FAILED'
            opt_run.error_message = str(e)
            opt_run.completed_at = timezone.now()
            opt_run.save()
            raise

    def _get_baseline_config(self):
        """Get current active configuration as baseline"""
        return StrategyConfigHistory.objects.filter(
            volatility_level=self.volatility_level,
            status='ACTIVE'
        ).order_by('-created_at').first()

    def _evaluate_current_config(self, config):
        """Evaluate current configuration performance"""
        if config and config.backtest_run:
            backtest = config.backtest_run
            return {
                'win_rate': float(backtest.win_rate or 0),
                'profit_factor': float(backtest.profit_factor or 0),
                'sharpe_ratio': float(backtest.sharpe_ratio or 0),
                'roi': float(backtest.roi or 0),
                'max_drawdown': float(backtest.max_drawdown or 0),
                'total_trades': backtest.total_trades or 0
            }

        # If no baseline, use default metrics
        return {
            'win_rate': 0,
            'profit_factor': 0,
            'sharpe_ratio': 0,
            'roi': 0,
            'max_drawdown': 0,
            'total_trades': 0
        }

    def _generate_candidate_configs(self, baseline_config):
        """
        Generate candidate configurations by varying parameters.

        Uses grid search around baseline parameters:
        - RSI: ±5 from baseline
        - ADX: ±2 from baseline
        - SL multiplier: ±0.2 from baseline
        - TP multiplier: ±0.3 from baseline
        """
        if baseline_config:
            base_params = baseline_config.parameters
        else:
            # Default baseline for volatility level
            base_params = self._get_default_params_for_volatility()

        candidates = []

        # Parameter variation ranges
        rsi_variations = [-5, 0, 5]
        adx_variations = [-2, 0, 2]
        sl_variations = [-0.2, 0, 0.2]
        tp_variations = [-0.3, 0, 0.3]

        # Generate combinations (limit to reasonable number)
        import itertools

        combos = list(itertools.product(
            rsi_variations[:2],  # Limit combinations
            adx_variations[:2],
            sl_variations[:2],
            tp_variations[:2]
        ))

        # Skip the baseline combination (0,0,0,0)
        combos = [c for c in combos if c != (0, 0, 0, 0)]

        for rsi_var, adx_var, sl_var, tp_var in combos[:8]:  # Test max 8 candidates
            params = base_params.copy()

            # Apply variations
            params['long_rsi_entry'] = max(20, min(40,
                params.get('long_rsi_entry', 30) + rsi_var))
            params['long_adx_min'] = max(15, min(30,
                params.get('long_adx_min', 20) + adx_var))
            params['sl_atr_multiplier'] = max(0.5, min(3.0,
                params.get('sl_atr_multiplier', 1.5) + sl_var))
            params['tp_atr_multiplier'] = max(1.0, min(5.0,
                params.get('tp_atr_multiplier', 2.5) + tp_var))

            candidates.append(params)

        return candidates

    def _run_backtest(self, symbols, config, lookback_days):
        """
        Run backtest with given configuration.

        Returns metrics dict or None if backtest fails.
        """
        try:
            from signals.services.backtest_service import BacktestService

            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=lookback_days)

            # Run backtest
            backtest_service = BacktestService(user=self.user)
            backtest = backtest_service.run_backtest(
                symbols=symbols,
                timeframe='15m',
                start_date=start_date,
                end_date=end_date,
                strategy_params=config,
                name=f"Optimization_{self.run_id}"
            )

            if backtest and backtest.status == 'COMPLETED':
                return {
                    'win_rate': float(backtest.win_rate or 0),
                    'profit_factor': float(backtest.profit_factor or 0),
                    'sharpe_ratio': float(backtest.sharpe_ratio or 0),
                    'roi': float(backtest.roi or 0),
                    'max_drawdown': float(backtest.max_drawdown or 0),
                    'total_trades': backtest.total_trades or 0,
                    'winning_trades': backtest.winning_trades or 0,
                    'losing_trades': backtest.losing_trades or 0
                }

            return None

        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}")
            return None

    def _get_symbols_for_volatility(self):
        """Get appropriate symbols for volatility level"""
        volatility_symbols = {
            'HIGH': ['DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT'],
            'MEDIUM': ['SOLUSDT', 'ADAUSDT', 'AVAXUSDT'],
            'LOW': ['BTCUSDT', 'ETHUSDT'],
            'ALL': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']
        }
        return volatility_symbols.get(self.volatility_level, ['BTCUSDT', 'ETHUSDT'])

    def _get_default_params_for_volatility(self):
        """Get default parameters for volatility level"""
        defaults = {
            'HIGH': {
                'long_rsi_entry': 35,
                'long_rsi_exit': 65,
                'long_adx_min': 18,
                'sl_atr_multiplier': 2.0,
                'tp_atr_multiplier': 3.5,
                'use_trailing_stop': True
            },
            'MEDIUM': {
                'long_rsi_entry': 30,
                'long_rsi_exit': 70,
                'long_adx_min': 22,
                'sl_atr_multiplier': 1.5,
                'tp_atr_multiplier': 2.5,
                'use_trailing_stop': True
            },
            'LOW': {
                'long_rsi_entry': 28,
                'long_rsi_exit': 72,
                'long_adx_min': 20,
                'sl_atr_multiplier': 1.0,
                'tp_atr_multiplier': 2.0,
                'use_trailing_stop': False
            }
        }
        return defaults.get(self.volatility_level, defaults['MEDIUM'])

    def _get_next_version(self):
        """Get next version number for this volatility level"""
        latest = StrategyConfigHistory.objects.filter(
            volatility_level=self.volatility_level
        ).order_by('-version').first()

        return (latest.version + 1) if latest else 1


class TradeCounterService:
    """
    Service to track trade counts and trigger optimization.
    Should be called after each trade closes.
    """

    @staticmethod
    def increment_and_check(volatility_level='ALL'):
        """
        Increment trade counter and check if optimization should be triggered.

        Args:
            volatility_level: Volatility level for this trade

        Returns:
            bool: True if optimization should be triggered
        """
        counter, created = TradeCounter.objects.get_or_create(
            volatility_level=volatility_level,
            defaults={'threshold': 200}
        )

        should_optimize = counter.increment()

        if should_optimize:
            logger.info(f"🎯 Trade threshold reached for {volatility_level}: {counter.trade_count}/{counter.threshold}")
            logger.info("   Triggering optimization cycle...")
            return True

        logger.debug(f"Trade count for {volatility_level}: {counter.trade_count}/{counter.threshold}")
        return False

    @staticmethod
    def reset_counter(volatility_level='ALL'):
        """Reset trade counter after optimization"""
        try:
            counter = TradeCounter.objects.get(volatility_level=volatility_level)
            counter.reset()
            logger.info(f"✅ Trade counter reset for {volatility_level}")
        except TradeCounter.DoesNotExist:
            logger.warning(f"Trade counter not found for {volatility_level}")

    @staticmethod
    def get_counter_status():
        """Get status of all trade counters"""
        counters = TradeCounter.objects.all()
        return [
            {
                'volatility_level': c.volatility_level,
                'count': c.trade_count,
                'threshold': c.threshold,
                'percentage': (c.trade_count / c.threshold * 100) if c.threshold > 0 else 0,
                'last_optimization': c.last_optimization.isoformat() if c.last_optimization else None
            }
            for c in counters
        ]


def compare_configs(config_a, config_b):
    """
    Compare two configurations and return comparison metrics.

    Args:
        config_a: StrategyConfigHistory instance
        config_b: StrategyConfigHistory instance

    Returns:
        dict with comparison results
    """
    score_a = config_a.calculate_fitness_score()
    score_b = config_b.calculate_fitness_score()

    improvement_pct = ((score_b - score_a) / score_a * 100) if score_a > 0 else 0

    return {
        'config_a': {
            'name': config_a.config_name,
            'version': config_a.version,
            'score': score_a,
            'metrics': config_a.metrics
        },
        'config_b': {
            'name': config_b.config_name,
            'version': config_b.version,
            'score': score_b,
            'metrics': config_b.metrics
        },
        'improvement_percentage': improvement_pct,
        'winner': 'config_b' if score_b > score_a else 'config_a'
    }


def update_config_if_better(new_config, baseline_config=None, threshold=5.0):
    """
    Update configuration if new config is better than baseline.

    Args:
        new_config: New StrategyConfigHistory to evaluate
        baseline_config: Current active config (optional, will fetch if None)
        threshold: Minimum improvement percentage required (default 5%)

    Returns:
        tuple: (applied: bool, improvement: float)
    """
    if baseline_config is None:
        baseline_config = StrategyConfigHistory.objects.filter(
            volatility_level=new_config.volatility_level,
            status='ACTIVE'
        ).order_by('-created_at').first()

    if baseline_config is None:
        # No baseline, apply new config
        new_config.mark_as_active()
        return True, 100.0

    comparison = compare_configs(baseline_config, new_config)
    improvement = comparison['improvement_percentage']

    if improvement >= threshold:
        logger.info(f"✅ Applying new config - improvement: {improvement:+.2f}%")
        new_config.improved = True
        new_config.improvement_percentage = Decimal(improvement)
        new_config.mark_as_active()
        return True, improvement
    else:
        logger.info(f"⏸️ Not applying new config - improvement below threshold: {improvement:+.2f}%")
        new_config.status = 'ARCHIVED'
        new_config.save()
        return False, improvement
