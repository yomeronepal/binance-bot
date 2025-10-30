"""
Monte Carlo Simulation Celery Tasks

Async tasks for running Monte Carlo simulations with statistical analysis.
"""

from celery import shared_task
from django.utils import timezone
from decimal import Decimal
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def run_montecarlo_simulation_async(self, simulation_id: int):
    """
    Run Monte Carlo simulation asynchronously.

    This task:
    1. Fetches historical data for the specified period
    2. Runs N simulations with randomized parameters
    3. Collects results from each simulation
    4. Calculates aggregate statistics
    5. Generates distribution data
    6. Assesses statistical robustness
    7. Stores all results in database

    Args:
        simulation_id: ID of the MonteCarloSimulation to run

    Returns:
        Dict with summary results
    """
    from signals.models_montecarlo import MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution
    from scanner.services.montecarlo_engine import MonteCarloEngine
    from scanner.strategies.signal_engine import SignalDetectionEngine
    from scanner.services.backtest_engine import BacktestEngine
    from scanner.services.historical_data_fetcher import HistoricalDataFetcher

    try:
        # Load simulation
        simulation = MonteCarloSimulation.objects.get(id=simulation_id)
        simulation.status = 'RUNNING'
        simulation.started_at = timezone.now()
        simulation.save()

        logger.info(f"Starting Monte Carlo simulation {simulation_id}: {simulation.name}")

        # Initialize engines
        mc_engine = MonteCarloEngine()
        data_fetcher = HistoricalDataFetcher()

        # === STEP 1: FETCH HISTORICAL DATA ===
        logger.info(f"Fetching historical data for symbols: {simulation.symbols}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        symbols_data = {}
        for symbol in simulation.symbols:
            klines = loop.run_until_complete(
                data_fetcher.fetch_historical_klines(
                    symbol=symbol,
                    interval=simulation.timeframe,
                    start_time=simulation.start_date,
                    end_time=simulation.end_date
                )
            )
            if klines:
                symbols_data[symbol] = klines
                logger.info(f"Fetched {len(klines)} candles for {symbol}")

        if not symbols_data:
            raise ValueError("No historical data found for any symbol")

        # === STEP 2: RUN SIMULATIONS ===
        logger.info(f"Running {simulation.num_simulations} Monte Carlo simulations...")

        simulation_results = []
        completed_count = 0
        failed_count = 0

        for run_number in range(1, simulation.num_simulations + 1):
            try:
                # Generate randomized parameters
                randomized_params = mc_engine.randomize_parameters(
                    base_params=simulation.strategy_params,
                    randomization_config=simulation.randomization_config
                )

                logger.debug(f"Run {run_number}: Parameters = {randomized_params}")

                # Convert params to SignalConfig
                signal_config = _dict_to_signal_config(randomized_params)

                # Generate signals with randomized parameters
                engine = SignalDetectionEngine(signal_config)
                signals = []

                for symbol, klines in symbols_data.items():
                    engine.update_candles(symbol, klines)

                    for candle in klines:
                        signal = engine.analyze_candle(symbol, candle)
                        if signal:
                            signals.append(signal)

                logger.debug(f"Run {run_number}: Generated {len(signals)} signals")

                # Run backtest with these signals
                backtest_engine = BacktestEngine(
                    initial_capital=float(simulation.initial_capital),
                    position_size=float(simulation.position_size),
                    strategy_params=randomized_params
                )

                backtest_results = backtest_engine.run_backtest(symbols_data, signals)

                # Store individual run results
                run_result = {
                    'run_number': run_number,
                    'parameters_used': randomized_params,
                    'total_trades': backtest_results['total_trades'],
                    'winning_trades': backtest_results['winning_trades'],
                    'losing_trades': backtest_results['losing_trades'],
                    'win_rate': backtest_results['win_rate'],
                    'total_profit_loss': backtest_results['total_profit_loss'],
                    'roi': backtest_results['roi'],
                    'max_drawdown': backtest_results['max_drawdown'],
                    'max_drawdown_amount': backtest_results['max_drawdown_amount'],
                    'sharpe_ratio': backtest_results['sharpe_ratio'],
                    'profit_factor': backtest_results['profit_factor'],
                }

                # Save to database
                MonteCarloRun.objects.create(
                    simulation=simulation,
                    run_number=run_number,
                    parameters_used=randomized_params,
                    total_trades=backtest_results['total_trades'],
                    winning_trades=backtest_results['winning_trades'],
                    losing_trades=backtest_results['losing_trades'],
                    win_rate=Decimal(str(backtest_results['win_rate'])),
                    total_profit_loss=Decimal(str(backtest_results['total_profit_loss'])),
                    roi=Decimal(str(backtest_results['roi'])),
                    max_drawdown=Decimal(str(backtest_results['max_drawdown'])),
                    max_drawdown_amount=Decimal(str(backtest_results['max_drawdown_amount'])),
                    sharpe_ratio=Decimal(str(backtest_results['sharpe_ratio'])),
                    profit_factor=Decimal(str(backtest_results['profit_factor'])),
                )

                simulation_results.append(run_result)
                completed_count += 1

                # Update progress every 50 runs
                if run_number % 50 == 0:
                    simulation.completed_simulations = completed_count
                    simulation.failed_simulations = failed_count
                    simulation.save()
                    logger.info(f"Progress: {completed_count}/{simulation.num_simulations} simulations completed")

            except Exception as e:
                logger.error(f"Run {run_number} failed: {str(e)}")
                failed_count += 1
                continue

        # Final progress update
        simulation.completed_simulations = completed_count
        simulation.failed_simulations = failed_count
        simulation.save()

        logger.info(f"Completed {completed_count} simulations, {failed_count} failed")

        if completed_count == 0:
            raise ValueError("All simulations failed - no results to analyze")

        # === STEP 3: AGGREGATE RESULTS ===
        logger.info("Calculating aggregate statistics...")

        aggregated_stats = mc_engine.aggregate_simulation_results(simulation_results)

        # Update simulation with aggregated results
        simulation.mean_return = aggregated_stats['mean_return']
        simulation.median_return = aggregated_stats['median_return']
        simulation.std_deviation = aggregated_stats['std_deviation']
        simulation.variance = aggregated_stats['variance']

        simulation.confidence_95_lower = aggregated_stats['confidence_95_lower']
        simulation.confidence_95_upper = aggregated_stats['confidence_95_upper']
        simulation.confidence_99_lower = aggregated_stats['confidence_99_lower']
        simulation.confidence_99_upper = aggregated_stats['confidence_99_upper']

        simulation.probability_of_profit = aggregated_stats['probability_of_profit']
        simulation.probability_of_loss = aggregated_stats['probability_of_loss']

        simulation.value_at_risk_95 = aggregated_stats['value_at_risk_95']
        simulation.value_at_risk_99 = aggregated_stats['value_at_risk_99']

        simulation.best_case_return = aggregated_stats['best_case_return']
        simulation.worst_case_return = aggregated_stats['worst_case_return']

        simulation.mean_max_drawdown = aggregated_stats['mean_max_drawdown']
        simulation.worst_case_drawdown = aggregated_stats['worst_case_drawdown']
        simulation.best_case_drawdown = aggregated_stats['best_case_drawdown']

        simulation.mean_sharpe_ratio = aggregated_stats['mean_sharpe_ratio']
        simulation.median_sharpe_ratio = aggregated_stats['median_sharpe_ratio']
        simulation.mean_win_rate = aggregated_stats['mean_win_rate']
        simulation.median_win_rate = aggregated_stats['median_win_rate']

        simulation.is_statistically_robust = aggregated_stats['is_statistically_robust']
        simulation.robustness_score = aggregated_stats['robustness_score']
        simulation.robustness_reasons = aggregated_stats['robustness_reasons']

        # === STEP 4: GENERATE DISTRIBUTION DATA ===
        logger.info("Generating distribution data for visualizations...")

        # Extract values for distributions
        rois = [float(r['roi']) for r in simulation_results]
        drawdowns = [float(r['max_drawdown']) for r in simulation_results]
        win_rates = [float(r['win_rate']) for r in simulation_results]
        sharpe_ratios = [float(r['sharpe_ratio']) for r in simulation_results]
        profit_factors = [float(r['profit_factor']) for r in simulation_results]
        total_trades_list = [int(r['total_trades']) for r in simulation_results]

        distributions_to_create = [
            ('ROI', rois),
            ('DRAWDOWN', drawdowns),
            ('WIN_RATE', win_rates),
            ('SHARPE', sharpe_ratios),
            ('PROFIT_FACTOR', profit_factors),
            ('TOTAL_TRADES', total_trades_list),
        ]

        for metric_name, values in distributions_to_create:
            if not values:
                continue

            # Generate histogram
            bins, frequencies = mc_engine.generate_histogram_data(values, num_bins=30)

            # Calculate distribution stats
            dist_stats = mc_engine.calculate_statistics(values)
            percentiles = mc_engine.calculate_percentiles(values)

            # Create distribution record
            MonteCarloDistribution.objects.create(
                simulation=simulation,
                metric=metric_name,
                bins=bins,
                frequencies=frequencies,
                mean=dist_stats['mean'],
                median=dist_stats['median'],
                std_dev=dist_stats['std_dev'],
                percentile_5=percentiles['p5'],
                percentile_25=percentiles['p25'],
                percentile_75=percentiles['p75'],
                percentile_95=percentiles['p95'],
            )

        # === STEP 5: FINALIZE ===
        simulation.status = 'COMPLETED'
        simulation.completed_at = timezone.now()
        simulation.save()

        execution_time = simulation.execution_time_seconds()
        logger.info(
            f"Monte Carlo simulation {simulation_id} completed successfully in {execution_time:.2f}s. "
            f"Completed: {completed_count}, Failed: {failed_count}, "
            f"Mean ROI: {simulation.mean_return}%, "
            f"Probability of Profit: {simulation.probability_of_profit}%, "
            f"Robust: {simulation.is_statistically_robust}"
        )

        return {
            'simulation_id': simulation_id,
            'status': 'COMPLETED',
            'completed_simulations': completed_count,
            'failed_simulations': failed_count,
            'mean_return': float(simulation.mean_return),
            'probability_of_profit': float(simulation.probability_of_profit),
            'is_statistically_robust': simulation.is_statistically_robust,
            'robustness_score': float(simulation.robustness_score),
            'execution_time_seconds': execution_time,
        }

    except Exception as e:
        logger.error(f"Monte Carlo simulation {simulation_id} failed: {str(e)}", exc_info=True)

        # Mark as failed
        try:
            simulation = MonteCarloSimulation.objects.get(id=simulation_id)
            simulation.status = 'FAILED'
            simulation.error_message = str(e)
            simulation.completed_at = timezone.now()
            simulation.save()
        except Exception as save_error:
            logger.error(f"Failed to save error state: {str(save_error)}")

        # Re-raise for Celery
        raise


def _dict_to_signal_config(params: dict):
    """
    Convert parameter dictionary to SignalConfig object.

    Args:
        params: Dictionary of strategy parameters

    Returns:
        SignalConfig instance
    """
    from scanner.strategies.signal_engine import SignalConfig

    # Extract RSI thresholds
    rsi_oversold = params.get('rsi_oversold', 30)
    rsi_overbought = params.get('rsi_overbought', 70)

    # Create SignalConfig with proper field mapping
    return SignalConfig(
        # LONG signal thresholds (RSI above 50, trending up)
        long_rsi_min=50.0,
        long_rsi_max=float(rsi_overbought),
        long_adx_min=params.get('adx_min', 20.0),
        long_volume_multiplier=params.get('volume_multiplier', 1.2),
        long_min_confidence=params.get('min_confidence', 0.7),

        # SHORT signal thresholds (RSI below 50, trending down)
        short_rsi_min=float(rsi_oversold),
        short_rsi_max=50.0,
        short_adx_min=params.get('adx_min', 20.0),
        short_volume_multiplier=params.get('volume_multiplier', 1.2),
        short_min_confidence=params.get('min_confidence', 0.7),

        # Stop Loss / Take Profit (ATR-based)
        sl_atr_multiplier=params.get('sl_atr_multiplier', 1.5),
        tp_atr_multiplier=params.get('tp_atr_multiplier', 2.5),

        # Trailing Stop
        use_trailing_stop=params.get('use_trailing_stop', True),
        trailing_stop_activation=params.get('trailing_stop_activation', 1.0),
        trailing_stop_distance=params.get('trailing_stop_distance', 0.5),
    )
