"""
ML-Based Tuning Celery Tasks

Async tasks for machine learning parameter optimization.
"""

from celery import shared_task
from django.utils import timezone
from decimal import Decimal
import logging
import asyncio
import os
import pickle
import joblib
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def run_ml_tuning_async(self, tuning_job_id: int):
    """
    Run ML-based parameter tuning asynchronously.

    This task:
    1. Generates parameter samples using Latin Hypercube Sampling
    2. Runs backtest for each sample to collect training data
    3. Extracts features from parameters and results
    4. Trains ML model on collected data
    5. Finds optimal parameters using trained model
    6. Validates on out-of-sample period
    7. Saves model artifacts for reuse

    Args:
        tuning_job_id: ID of the MLTuningJob to run

    Returns:
        Dict with summary results
    """
    from signals.models_mltuning import MLTuningJob, MLTuningSample, MLPrediction
    from scanner.services.ml_tuning_engine import MLTuningEngine
    from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
    from scanner.services.backtest_engine import BacktestEngine
    from scanner.services.historical_data_fetcher import HistoricalDataFetcher

    try:
        # Load tuning job
        tuning_job = MLTuningJob.objects.get(id=tuning_job_id)
        tuning_job.status = 'RUNNING'
        tuning_job.started_at = timezone.now()
        tuning_job.save()

        logger.info(f"Starting ML tuning job {tuning_job_id}: {tuning_job.name}")

        # Initialize ML engine
        ml_engine = MLTuningEngine(ml_algorithm=tuning_job.ml_algorithm)
        data_fetcher = HistoricalDataFetcher()

        # === STEP 1: FETCH HISTORICAL DATA ===
        logger.info(f"Fetching training data for symbols: {tuning_job.symbols}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Fetch training period data
        training_data = {}
        for symbol in tuning_job.symbols:
            klines = loop.run_until_complete(
                data_fetcher.fetch_historical_klines(
                    symbol=symbol,
                    interval=tuning_job.timeframe,
                    start_time=tuning_job.training_start_date,
                    end_time=tuning_job.training_end_date
                )
            )
            if klines:
                training_data[symbol] = klines
                logger.info(f"Fetched {len(klines)} training candles for {symbol}")

        # Fetch validation period data if specified
        validation_data = None
        if tuning_job.validation_start_date and tuning_job.validation_end_date:
            validation_data = {}
            for symbol in tuning_job.symbols:
                klines = loop.run_until_complete(
                    data_fetcher.fetch_historical_klines(
                        symbol=symbol,
                        interval=tuning_job.timeframe,
                        start_time=tuning_job.validation_start_date,
                        end_time=tuning_job.validation_end_date
                    )
                )
                if klines:
                    validation_data[symbol] = klines
                    logger.info(f"Fetched {len(klines)} validation candles for {symbol}")

        if not training_data:
            raise ValueError("No training data found for any symbol")

        # === STEP 2: GENERATE PARAMETER SAMPLES ===
        logger.info(f"Generating {tuning_job.num_training_samples} parameter samples...")

        parameter_samples = ml_engine.generate_parameter_samples(
            parameter_space=tuning_job.parameter_space,
            num_samples=tuning_job.num_training_samples,
            method='latin_hypercube'
        )

        logger.info(f"Generated {len(parameter_samples)} parameter samples")

        # === STEP 3: RUN BACKTESTS FOR EACH SAMPLE ===
        logger.info("Running backtests for each parameter sample...")

        training_samples = []
        successful_count = 0
        failed_count = 0

        for idx, params in enumerate(parameter_samples, 1):
            try:
                # Convert params to SignalConfig
                signal_config = _dict_to_signal_config(params)

                # Generate signals
                engine = SignalDetectionEngine(signal_config)
                signals = []

                for symbol, klines in training_data.items():
                    engine.update_candles(symbol, klines)
                    for candle in klines:
                        signal = engine.analyze_candle(symbol, candle)
                        if signal:
                            signals.append(signal)

                # Run backtest
                backtest_engine = BacktestEngine(
                    initial_capital=float(tuning_job.initial_capital),
                    position_size=float(tuning_job.position_size),
                    strategy_params=params
                )

                backtest_results = backtest_engine.run_backtest(training_data, signals)

                # Extract features
                features = ml_engine.extract_features(
                    parameters=params,
                    market_data=None,
                    use_technical_indicators=tuning_job.use_technical_indicators,
                    use_market_conditions=tuning_job.use_market_conditions,
                    use_temporal_features=tuning_job.use_temporal_features
                )

                # Determine target value based on optimization metric
                target_value = _get_target_value(
                    backtest_results,
                    tuning_job.optimization_metric
                )

                # Store sample
                sample_data = {
                    'parameters': params,
                    'features': features,
                    'roi': backtest_results['roi'],
                    'sharpe_ratio': backtest_results['sharpe_ratio'],
                    'profit_factor': backtest_results['profit_factor'],
                    'win_rate': backtest_results['win_rate'],
                    'max_drawdown': backtest_results['max_drawdown'],
                    'total_trades': backtest_results['total_trades'],
                    'target_value': target_value
                }

                training_samples.append(sample_data)

                # Save to database
                MLTuningSample.objects.create(
                    tuning_job=tuning_job,
                    sample_number=idx,
                    parameters=params,
                    features=features,
                    roi=Decimal(str(backtest_results['roi'])),
                    sharpe_ratio=Decimal(str(backtest_results['sharpe_ratio'])),
                    profit_factor=Decimal(str(backtest_results['profit_factor'])),
                    win_rate=Decimal(str(backtest_results['win_rate'])),
                    max_drawdown=Decimal(str(backtest_results['max_drawdown'])),
                    total_trades=backtest_results['total_trades'],
                    target_value=Decimal(str(target_value)),
                    split_set='TRAIN'
                )

                successful_count += 1

                # Update progress every 50 samples
                if idx % 50 == 0:
                    tuning_job.samples_evaluated = idx
                    tuning_job.samples_successful = successful_count
                    tuning_job.samples_failed = failed_count
                    tuning_job.save()
                    logger.info(f"Progress: {idx}/{tuning_job.num_training_samples} samples completed")

            except Exception as e:
                logger.error(f"Sample {idx} failed: {str(e)}")
                failed_count += 1
                continue

        # Final progress update
        tuning_job.samples_evaluated = len(parameter_samples)
        tuning_job.samples_successful = successful_count
        tuning_job.samples_failed = failed_count
        tuning_job.save()

        logger.info(f"Data collection complete: {successful_count} successful, {failed_count} failed")

        if successful_count < 100:
            raise ValueError(f"Too few successful samples ({successful_count}). Need at least 100.")

        # === STEP 4: SPLIT DATA ===
        logger.info("Splitting data into train/validation/test sets...")

        import random
        random.shuffle(training_samples)

        train_ratio = float(tuning_job.train_test_split)
        val_ratio = (1 - train_ratio) / 2
        test_ratio = (1 - train_ratio) / 2

        n_samples = len(training_samples)
        n_train = int(n_samples * train_ratio)
        n_val = int(n_samples * val_ratio)

        train_samples = training_samples[:n_train]
        val_samples = training_samples[n_train:n_train + n_val]
        test_samples = training_samples[n_train + n_val:]

        logger.info(f"Split: {len(train_samples)} train, {len(val_samples)} val, {len(test_samples)} test")

        # === STEP 5: TRAIN ML MODEL ===
        logger.info(f"Training {tuning_job.ml_algorithm} model...")

        X_train, y_train, feature_names = ml_engine.prepare_training_data(
            train_samples,
            tuning_job.optimization_metric
        )

        X_val, y_val, _ = ml_engine.prepare_training_data(
            val_samples,
            tuning_job.optimization_metric
        ) if val_samples else (None, None, None)

        X_test, y_test, _ = ml_engine.prepare_training_data(
            test_samples,
            tuning_job.optimization_metric
        ) if test_samples else (None, None, None)

        # Train model
        model, scaler, scores = ml_engine.train_model(
            X_train, y_train,
            X_val, y_val,
            hyperparameters=tuning_job.ml_hyperparameters
        )

        ml_engine.feature_names = feature_names

        logger.info(f"Training complete. Train R²: {scores['train_r2']:.3f}, Val R²: {scores.get('val_r2', 0):.3f}")

        # Calculate test score if available
        if X_test is not None:
            from sklearn.metrics import r2_score
            y_test_pred = model.predict(scaler.transform(X_test))
            scores['test_r2'] = r2_score(y_test, y_test_pred)

        # Update tuning job with training results
        tuning_job.training_score = Decimal(str(scores['train_r2']))
        tuning_job.validation_score = Decimal(str(scores.get('val_r2', 0)))
        tuning_job.test_score = Decimal(str(scores.get('test_r2', 0)))

        # === STEP 6: ASSESS MODEL QUALITY ===
        logger.info("Assessing model quality...")

        is_production_ready, quality_score, quality_reasons = ml_engine.assess_model_quality(scores)

        tuning_job.overfitting_score = Decimal(str(scores.get('overfitting', 0) * 100))
        tuning_job.model_confidence = quality_score
        tuning_job.is_production_ready = is_production_ready

        logger.info(f"Quality: {quality_score}/100, Production Ready: {is_production_ready}")

        # === STEP 7: GET FEATURE IMPORTANCE ===
        logger.info("Calculating feature importance...")

        feature_importance = ml_engine.get_feature_importance()
        tuning_job.feature_importance = feature_importance

        # === STEP 8: FIND OPTIMAL PARAMETERS ===
        logger.info("Finding optimal parameters...")

        optimal_candidates = ml_engine.find_optimal_parameters(
            parameter_space=tuning_job.parameter_space,
            num_candidates=10000
        )

        # Get best parameters
        best_params, predicted_performance, confidence = optimal_candidates[0]

        tuning_job.best_parameters = best_params
        tuning_job.predicted_performance = Decimal(str(predicted_performance))

        logger.info(f"Best parameters found: Predicted {tuning_job.optimization_metric} = {predicted_performance:.4f}")

        # === STEP 9: CALCULATE PARAMETER SENSITIVITY ===
        logger.info("Calculating parameter sensitivity...")

        parameter_sensitivity = ml_engine.calculate_parameter_sensitivity(
            base_parameters=best_params,
            parameter_space=tuning_job.parameter_space,
            num_samples=100
        )

        tuning_job.parameter_sensitivity = parameter_sensitivity

        # === STEP 10: OUT-OF-SAMPLE VALIDATION ===
        if validation_data:
            logger.info("Running out-of-sample validation...")

            try:
                # Test best parameters on validation data
                signal_config = _dict_to_signal_config(best_params)
                engine = SignalDetectionEngine(signal_config)
                signals = []

                for symbol, klines in validation_data.items():
                    engine.update_candles(symbol, klines)
                    for candle in klines:
                        signal = engine.analyze_candle(symbol, candle)
                        if signal:
                            signals.append(signal)

                backtest_engine = BacktestEngine(
                    initial_capital=float(tuning_job.initial_capital),
                    position_size=float(tuning_job.position_size),
                    strategy_params=best_params
                )

                val_results = backtest_engine.run_backtest(validation_data, signals)

                # Update with validation results
                tuning_job.out_of_sample_roi = Decimal(str(val_results['roi']))
                tuning_job.out_of_sample_sharpe = Decimal(str(val_results['sharpe_ratio']))
                tuning_job.out_of_sample_win_rate = Decimal(str(val_results['win_rate']))
                tuning_job.out_of_sample_max_drawdown = Decimal(str(val_results['max_drawdown']))

                logger.info(f"Validation: ROI {val_results['roi']:.2f}%, Sharpe {val_results['sharpe_ratio']:.2f}")

            except Exception as e:
                logger.error(f"Validation failed: {str(e)}")

        # === STEP 11: SAVE MODEL ARTIFACTS ===
        logger.info("Saving model artifacts...")

        # Create models directory if it doesn't exist
        models_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ml_models')
        os.makedirs(models_dir, exist_ok=True)

        # Save model
        model_filename = f"mltuning_{tuning_job_id}_model.pkl"
        model_path = os.path.join(models_dir, model_filename)
        joblib.dump(model, model_path)
        tuning_job.model_file_path = model_path

        # Save scaler
        scaler_filename = f"mltuning_{tuning_job_id}_scaler.pkl"
        scaler_path = os.path.join(models_dir, scaler_filename)
        joblib.dump(scaler, scaler_path)
        tuning_job.scaler_file_path = scaler_path

        logger.info(f"Model artifacts saved to {models_dir}")

        # === STEP 12: FINALIZE ===
        tuning_job.status = 'COMPLETED'
        tuning_job.completed_at = timezone.now()
        tuning_job.save()

        execution_time = tuning_job.execution_time_seconds()
        logger.info(
            f"ML tuning job {tuning_job_id} completed in {execution_time:.2f}s. "
            f"Quality: {quality_score}/100, Production Ready: {is_production_ready}"
        )

        return {
            'tuning_job_id': tuning_job_id,
            'status': 'COMPLETED',
            'samples_successful': successful_count,
            'samples_failed': failed_count,
            'training_score': float(tuning_job.training_score),
            'validation_score': float(tuning_job.validation_score),
            'is_production_ready': is_production_ready,
            'quality_score': float(quality_score),
            'best_parameters': best_params,
            'predicted_performance': float(predicted_performance),
            'execution_time_seconds': execution_time,
        }

    except Exception as e:
        logger.error(f"ML tuning job {tuning_job_id} failed: {str(e)}", exc_info=True)

        # Mark as failed
        try:
            tuning_job = MLTuningJob.objects.get(id=tuning_job_id)
            tuning_job.status = 'FAILED'
            tuning_job.error_message = str(e)
            tuning_job.completed_at = timezone.now()
            tuning_job.save()
        except Exception as save_error:
            logger.error(f"Failed to save error state: {str(save_error)}")

        # Re-raise for Celery
        raise


def _dict_to_signal_config(params: dict) -> 'SignalConfig':
    """Convert parameter dictionary to SignalConfig object."""
    from scanner.strategies.signal_engine import SignalConfig

    rsi_oversold = params.get('rsi_oversold', 30)
    rsi_overbought = params.get('rsi_overbought', 70)

    return SignalConfig(
        long_rsi_min=50.0,
        long_rsi_max=float(rsi_overbought),
        long_adx_min=params.get('adx_min', 20.0),
        long_volume_multiplier=params.get('volume_multiplier', 1.2),
        long_min_confidence=params.get('min_confidence', 0.7),

        short_rsi_min=float(rsi_oversold),
        short_rsi_max=50.0,
        short_adx_min=params.get('adx_min', 20.0),
        short_volume_multiplier=params.get('volume_multiplier', 1.2),
        short_min_confidence=params.get('min_confidence', 0.7),

        sl_atr_multiplier=params.get('sl_atr_multiplier', 1.5),
        tp_atr_multiplier=params.get('tp_atr_multiplier', 2.5),

        use_trailing_stop=params.get('use_trailing_stop', True),
        trailing_stop_activation=params.get('trailing_stop_activation', 1.0),
        trailing_stop_distance=params.get('trailing_stop_distance', 0.5),
    )


def _get_target_value(backtest_results: Dict, optimization_metric: str) -> float:
    """Extract target value based on optimization metric."""
    metric_mapping = {
        'ROI': 'roi',
        'SHARPE_RATIO': 'sharpe_ratio',
        'PROFIT_FACTOR': 'profit_factor',
        'WIN_RATE': 'win_rate',
        'RISK_ADJUSTED_RETURN': None  # Calculated below
    }

    if optimization_metric == 'RISK_ADJUSTED_RETURN':
        roi = backtest_results.get('roi', 0)
        max_dd = backtest_results.get('max_drawdown', 0)
        return roi / (abs(max_dd) + 1) if max_dd != 0 else roi

    metric_key = metric_mapping.get(optimization_metric, 'sharpe_ratio')
    return backtest_results.get(metric_key, 0)
