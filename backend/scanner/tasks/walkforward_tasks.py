"""
Walk-Forward Optimization Celery Tasks
Background tasks for running walk-forward analysis.
"""
from celery import shared_task
from decimal import Decimal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def run_walkforward_optimization_async(self, walkforward_id: int):
    """
    Run walk-forward optimization asynchronously.

    Process:
    1. Load walk-forward configuration
    2. Generate windows
    3. For each window:
       a. Run optimization on training period
       b. Run backtest on testing period with best parameters
    4. Aggregate results and assess robustness
    """
    from signals.models_walkforward import WalkForwardOptimization, WalkForwardWindow, WalkForwardMetric
    from scanner.services.walkforward_engine import WalkForwardEngine
    from scanner.services.parameter_optimizer import ParameterOptimizer
    from scanner.services.backtest_engine import BacktestEngine
    from scanner.services.historical_data_fetcher import HistoricalDataFetcher
    from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
    import asyncio

    try:
        # Load walk-forward configuration
        walkforward = WalkForwardOptimization.objects.get(id=walkforward_id)
        walkforward.status = 'RUNNING'
        walkforward.started_at = datetime.now()
        walkforward.save()

        logger.info(f"Starting walk-forward optimization: {walkforward.name} (ID: {walkforward_id})")

        # Initialize engine
        wf_engine = WalkForwardEngine()

        # Generate windows
        windows = wf_engine.generate_windows(
            walkforward.start_date,
            walkforward.end_date,
            walkforward.training_window_days,
            walkforward.testing_window_days,
            walkforward.step_days
        )

        walkforward.total_windows = len(windows)
        walkforward.save()

        logger.info(f"Generated {len(windows)} windows for walk-forward analysis")

        # Create window records in database
        window_records = []
        for window_config in windows:
            window_record = WalkForwardWindow.objects.create(
                walk_forward=walkforward,
                window_number=window_config['window_number'],
                training_start=window_config['training_start'],
                training_end=window_config['training_end'],
                testing_start=window_config['testing_start'],
                testing_end=window_config['testing_end'],
                status='PENDING'
            )
            window_records.append(window_record)

        # Process each window
        window_results = []

        for idx, (window_config, window_record) in enumerate(zip(windows, window_records)):
            logger.info(f"Processing window {window_config['window_number']}/{len(windows)}")

            try:
                window_record.status = 'OPTIMIZING'
                window_record.save()

                # === OPTIMIZATION PHASE (In-Sample) ===
                logger.info(f"  Optimizing parameters on training data...")

                # Fetch historical data for training period
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                historical_fetcher = HistoricalDataFetcher()
                symbols_data_train = loop.run_until_complete(
                    historical_fetcher.fetch_multiple_symbols(
                        walkforward.symbols,
                        walkforward.timeframe,
                        window_config['training_start'],
                        window_config['training_end']
                    )
                )

                # Run parameter optimization
                optimizer = ParameterOptimizer()
                optimization_results = loop.run_until_complete(
                    optimizer.optimize_parameters(
                        symbols=walkforward.symbols,
                        timeframe=walkforward.timeframe,
                        start_date=window_config['training_start'],
                        end_date=window_config['training_end'],
                        parameter_ranges=walkforward.parameter_ranges,
                        search_method=walkforward.optimization_method,
                        initial_capital=float(walkforward.initial_capital),
                        position_size=float(walkforward.position_size),
                        max_combinations=50  # Limit to avoid excessive computation
                    )
                )

                # Get best parameters from optimization
                if not optimization_results:
                    raise Exception("Optimization returned no results")

                best_result = optimization_results[0]  # Already sorted by score
                best_params = best_result['params']

                # Store in-sample results
                window_record.best_params = best_params
                window_record.in_sample_total_trades = best_result['total_trades']
                window_record.in_sample_win_rate = Decimal(str(best_result['win_rate']))
                window_record.in_sample_roi = Decimal(str(best_result['roi']))
                window_record.in_sample_sharpe = Decimal(str(best_result.get('sharpe_ratio', 0))) if best_result.get('sharpe_ratio') else None
                window_record.in_sample_max_drawdown = Decimal(str(best_result.get('max_drawdown', 0)))
                window_record.save()

                logger.info(f"  In-sample: {best_result['total_trades']} trades, {best_result['win_rate']:.2f}% WR, {best_result['roi']:.2f}% ROI")

                # === TESTING PHASE (Out-of-Sample) ===
                window_record.status = 'TESTING'
                window_record.save()

                logger.info(f"  Testing parameters on out-of-sample data...")

                # Fetch historical data for testing period
                symbols_data_test = loop.run_until_complete(
                    historical_fetcher.fetch_multiple_symbols(
                        walkforward.symbols,
                        walkforward.timeframe,
                        window_config['testing_start'],
                        window_config['testing_end']
                    )
                )

                # Generate signals using best parameters
                signal_config = _dict_to_signal_config(best_params)
                engine = SignalDetectionEngine(signal_config)
                signals = []

                for symbol, klines in symbols_data_test.items():
                    engine.update_candles(symbol, klines)
                    for candle in klines:
                        signal = engine.analyze_candle(symbol, candle)
                        if signal:
                            signals.append(signal)

                # Run backtest with best parameters on testing period
                backtest_engine = BacktestEngine(
                    initial_capital=float(walkforward.initial_capital),
                    position_size=float(walkforward.position_size),
                    strategy_params=best_params
                )

                test_results = backtest_engine.run_backtest(symbols_data_test, signals)

                # Store out-of-sample results
                window_record.out_sample_total_trades = test_results['total_trades']
                window_record.out_sample_win_rate = Decimal(str(test_results['win_rate']))
                window_record.out_sample_roi = Decimal(str(test_results['roi']))
                window_record.out_sample_sharpe = Decimal(str(test_results.get('sharpe_ratio', 0))) if test_results.get('sharpe_ratio') else None
                window_record.out_sample_max_drawdown = Decimal(str(test_results.get('max_drawdown', 0)))

                # Calculate performance drop
                in_roi = float(window_record.in_sample_roi)
                out_roi = float(window_record.out_sample_roi)
                if in_roi != 0:
                    perf_drop = ((in_roi - out_roi) / abs(in_roi)) * 100
                    window_record.performance_drop_pct = Decimal(str(round(perf_drop, 2)))

                window_record.status = 'COMPLETED'
                window_record.save()

                logger.info(f"  Out-of-sample: {test_results['total_trades']} trades, {test_results['win_rate']:.2f}% WR, {test_results['roi']:.2f}% ROI")
                logger.info(f"  Performance drop: {window_record.performance_drop_pct:.2f}%")

                # Add to results for aggregation
                window_results.append({
                    'window_number': window_config['window_number'],
                    'in_sample_win_rate': window_record.in_sample_win_rate,
                    'out_sample_win_rate': window_record.out_sample_win_rate,
                    'in_sample_roi': window_record.in_sample_roi,
                    'out_sample_roi': window_record.out_sample_roi,
                })

                # Update progress
                walkforward.completed_windows = idx + 1
                walkforward.save()

                loop.close()

            except Exception as e:
                logger.error(f"Error processing window {window_config['window_number']}: {e}", exc_info=True)
                window_record.status = 'FAILED'
                window_record.error_message = str(e)
                window_record.save()
                continue

        # === AGGREGATE RESULTS ===
        logger.info("Aggregating results from all windows...")

        aggregate_metrics = wf_engine.calculate_aggregate_metrics(window_results)

        # Update walk-forward with aggregate results
        walkforward.avg_in_sample_win_rate = aggregate_metrics.get('avg_in_sample_win_rate', Decimal('0.00'))
        walkforward.avg_out_sample_win_rate = aggregate_metrics.get('avg_out_sample_win_rate', Decimal('0.00'))
        walkforward.avg_in_sample_roi = aggregate_metrics.get('avg_in_sample_roi', Decimal('0.00'))
        walkforward.avg_out_sample_roi = aggregate_metrics.get('avg_out_sample_roi', Decimal('0.00'))
        walkforward.performance_degradation = aggregate_metrics.get('performance_degradation', Decimal('0.00'))
        walkforward.consistency_score = aggregate_metrics.get('consistency_score', Decimal('0.00'))
        walkforward.is_robust = aggregate_metrics.get('is_robust', False)
        walkforward.robustness_notes = aggregate_metrics.get('robustness_notes', '')

        walkforward.status = 'COMPLETED'
        walkforward.completed_at = datetime.now()
        walkforward.save()

        logger.info(f"✅ Walk-forward optimization completed!")
        logger.info(f"  Average Out-of-Sample ROI: {walkforward.avg_out_sample_roi:.2f}%")
        logger.info(f"  Consistency Score: {walkforward.consistency_score:.0f}/100")
        logger.info(f"  Robust: {'✅ YES' if walkforward.is_robust else '❌ NO'}")

        return {
            'walkforward_id': walkforward_id,
            'status': 'COMPLETED',
            'is_robust': walkforward.is_robust,
            'avg_out_sample_roi': float(walkforward.avg_out_sample_roi),
            'consistency_score': float(walkforward.consistency_score),
        }

    except Exception as e:
        logger.error(f"Error in walk-forward optimization {walkforward_id}: {e}", exc_info=True)

        try:
            walkforward = WalkForwardOptimization.objects.get(id=walkforward_id)
            walkforward.status = 'FAILED'
            walkforward.error_message = str(e)
            walkforward.completed_at = datetime.now()
            walkforward.save()
        except Exception as save_error:
            logger.error(f"Failed to update walkforward status: {save_error}")

        raise self.retry(exc=e, countdown=60)


def _dict_to_signal_config(params: dict):
    """Convert parameter dictionary to SignalConfig object."""
    from scanner.strategies.signal_engine import SignalConfig

    # Map optimization parameters to SignalConfig fields
    # Parameters like rsi_period, rsi_oversold, rsi_overbought are converted to
    # SignalConfig's long_rsi_min, long_rsi_max, short_rsi_min, short_rsi_max

    rsi_oversold = params.get('rsi_oversold', 30)
    rsi_overbought = params.get('rsi_overbought', 70)

    return SignalConfig(
        # LONG signal thresholds (RSI above 50, trending up)
        long_rsi_min=50.0,
        long_rsi_max=float(rsi_overbought),
        long_adx_min=params.get('adx_min', 20.0),
        long_volume_multiplier=params.get('volume_multiplier', 1.2),

        # SHORT signal thresholds (RSI below 50, trending down)
        short_rsi_min=float(rsi_oversold),
        short_rsi_max=50.0,
        short_adx_min=params.get('adx_min', 20.0),
        short_volume_multiplier=params.get('volume_multiplier', 1.2),

        # Stop loss and take profit
        sl_atr_multiplier=params.get('sl_atr_multiplier', 1.5),
        tp_atr_multiplier=params.get('tp_atr_multiplier', 2.5),

        # Signal management
        min_confidence=params.get('min_confidence', 0.7),
        max_candles_cache=200,
    )
