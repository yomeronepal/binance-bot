"""
Walk-Forward Optimization Celery Tasks - OPTIMIZED VERSION
Enhanced with robustness metrics, market regime detection, and multi-objective optimization.
"""
from celery import shared_task
from decimal import Decimal
from datetime import datetime, timedelta
import logging
import numpy as np
from typing import Dict, List, Any, Tuple
import asyncio

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """Enhanced walk-forward optimization engine with robustness features"""
    
    # Optimization constraints
    OPTIMIZATION_CONSTRAINTS = {
        'min_trades_per_window': 10,
        'max_drawdown_limit': Decimal('0.15'),  # 15%
        'min_sharpe_ratio': Decimal('0.1'),
        'min_win_rate': Decimal('0.30'),  # 30%
        'min_profit_factor': Decimal('1.1'),
    }
    
    # Parameter ranges for normalization
    PARAMETER_RANGES = {
        'long_adx_min': (15.0, 40.0),
        'short_adx_min': (15.0, 40.0),
        'long_rsi_min': (15.0, 35.0),
        'long_rsi_max': (25.0, 45.0),
        'short_rsi_min': (55.0, 75.0),
        'short_rsi_max': (65.0, 85.0),
        'sl_atr_multiplier': (1.5, 4.0),
        'tp_atr_multiplier': (2.0, 10.0),
        'min_confidence': (0.6, 0.9),
    }

    def __init__(self):
        self.walkforward_engine = WalkForwardEngine()

    def calculate_composite_score(self, backtest_results: Dict) -> Decimal:
        """Calculate robust composite score for multi-objective optimization"""
        try:
            # Base metrics
            roi = Decimal(str(backtest_results.get('roi', 0)))
            sharpe = Decimal(str(backtest_results.get('sharpe_ratio', 0)))
            win_rate = Decimal(str(backtest_results.get('win_rate', 0)))
            max_drawdown = Decimal(str(backtest_results.get('max_drawdown', 0)))
            profit_factor = Decimal(str(backtest_results.get('profit_factor', 1)))
            trade_count = backtest_results.get('total_trades', 0)
            
            # Normalized scores
            roi_score = roi / Decimal('10.0')  # Normalize ROI
            sharpe_score = sharpe * Decimal('10.0')  # Boost Sharpe importance
            win_rate_score = (win_rate - Decimal('30.0')) / Decimal('70.0')  # 30% baseline
            profit_factor_score = profit_factor - Decimal('1.0')
            
            # Penalties
            drawdown_penalty = (max_drawdown / Decimal('5.0')) ** Decimal('2')  # Exponential penalty
            
            # Trade count optimization
            trade_penalty = Decimal('0')
            if trade_count < self.OPTIMIZATION_CONSTRAINTS['min_trades_per_window']:
                missing_trades = self.OPTIMIZATION_CONSTRAINTS['min_trades_per_window'] - trade_count
                trade_penalty = Decimal(str(missing_trades)) * Decimal('0.1')
            
            # Composite score with weights
            composite = (
                roi_score * Decimal('0.25') +           # 25% ROI
                sharpe_score * Decimal('0.25') +        # 25% Sharpe
                win_rate_score * Decimal('0.20') +      # 20% Win Rate
                profit_factor_score * Decimal('0.15') + # 15% Profit Factor
                -drawdown_penalty * Decimal('0.10') +   # 10% Drawdown penalty
                -trade_penalty * Decimal('0.05')        # 5% Trade count penalty
            )
            
            return max(Decimal('-100.0'), composite)  # Floor at -100
            
        except Exception as e:
            logger.error(f"Error calculating composite score: {e}")
            return Decimal('-100.0')

    def validate_optimization_result(self, result: Dict) -> Tuple[bool, str]:
        """Validate optimization results against multiple constraints"""
        try:
            # Trade count validation
            if result['total_trades'] < self.OPTIMIZATION_CONSTRAINTS['min_trades_per_window']:
                return False, f"Insufficient trades: {result['total_trades']}"
            
            # Drawdown validation
            max_drawdown = Decimal(str(result.get('max_drawdown', 0)))
            if max_drawdown > self.OPTIMIZATION_CONSTRAINTS['max_drawdown_limit']:
                return False, f"Excessive drawdown: {max_drawdown:.2%}"
            
            # Sharpe ratio validation
            sharpe_ratio = Decimal(str(result.get('sharpe_ratio', -1)))
            if sharpe_ratio < self.OPTIMIZATION_CONSTRAINTS['min_sharpe_ratio']:
                return False, f"Poor Sharpe ratio: {sharpe_ratio:.4f}"
            
            # Win rate validation
            win_rate = Decimal(str(result.get('win_rate', 0)))
            if win_rate < self.OPTIMIZATION_CONSTRAINTS['min_win_rate']:
                return False, f"Low win rate: {win_rate:.2%}"
            
            # Profit factor validation
            profit_factor = Decimal(str(result.get('profit_factor', 1)))
            if profit_factor < self.OPTIMIZATION_CONSTRAINTS['min_profit_factor']:
                return False, f"Poor profit factor: {profit_factor:.2f}"
            
            return True, "Valid"
            
        except Exception as e:
            return False, f"Validation error: {e}"

    def classify_market_regime(self, price_data: List[Dict]) -> str:
        """Classify market regime based on volatility and trend characteristics"""
        if not price_data or len(price_data) < 20:
            return "LOW_VOL_RANGE"
        
        try:
            prices = [float(candle['close']) for candle in price_data]
            returns = np.diff(np.log(prices))
            
            # Calculate metrics
            volatility = np.std(returns) * np.sqrt(365)  # Annualized volatility
            trend_strength = self._calculate_trend_strength(prices)
            
            # Regime classification thresholds
            high_vol_threshold = 0.6  # Adjusted for crypto
            strong_trend_threshold = 0.1
            
            if volatility > high_vol_threshold:
                if trend_strength > strong_trend_threshold:
                    return "HIGH_VOL_TREND"
                else:
                    return "HIGH_VOL_RANGE"
            else:
                if trend_strength > strong_trend_threshold:
                    return "LOW_VOL_TREND"
                else:
                    return "LOW_VOL_RANGE"
                    
        except Exception as e:
            logger.warning(f"Error classifying market regime: {e}")
            return "LOW_VOL_RANGE"

    def _calculate_trend_strength(self, prices: List[float]) -> float:
        """Calculate trend strength using linear regression"""
        if len(prices) < 10:
            return 0.0
        
        try:
            x = np.arange(len(prices))
            y = np.array(prices)
            
            # Linear regression
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]  # Trend direction and strength
            
            # Normalize slope by price level
            normalized_slope = abs(slope) / np.mean(y)
            return min(1.0, normalized_slope * 1000)  # Scale to reasonable range
            
        except Exception as e:
            logger.warning(f"Error calculating trend strength: {e}")
            return 0.0

    def calculate_parameter_stability(self, windows: List) -> Decimal:
        """Calculate parameter stability across windows"""
        if len(windows) < 2:
            return Decimal('100.00')
        
        try:
            valid_windows = [w for w in windows if w.best_params and w.status == 'COMPLETED']
            if len(valid_windows) < 2:
                return Decimal('0.00')
            
            valid_windows.sort(key=lambda x: x.window_number)
            param_changes = []
            
            for i in range(1, len(valid_windows)):
                change = self._calculate_parameter_distance(
                    valid_windows[i-1].best_params,
                    valid_windows[i].best_params
                )
                param_changes.append(change)
            
            if not param_changes:
                return Decimal('100.00')
                
            avg_change = sum(param_changes) / len(param_changes)
            stability_score = Decimal('100.00') * (Decimal('1.0') - Decimal(str(avg_change)))
            
            return max(Decimal('0.00'), min(Decimal('100.00'), stability_score))
            
        except Exception as e:
            logger.error(f"Error calculating parameter stability: {e}")
            return Decimal('0.00')

    def _calculate_parameter_distance(self, params1: Dict, params2: Dict) -> float:
        """Calculate normalized distance between parameter sets"""
        if not params1 or not params2:
            return 1.0
            
        try:
            total_distance = 0.0
            compared_params = 0
            
            for param_name, (min_val, max_val) in self.PARAMETER_RANGES.items():
                if param_name in params1 and param_name in params2:
                    val1 = params1[param_name]
                    val2 = params2[param_name]
                    
                    # Normalize difference by parameter range
                    param_range = max_val - min_val
                    if param_range > 0:
                        normalized_diff = abs(val1 - val2) / param_range
                        total_distance += min(1.0, normalized_diff)  # Cap at 1.0
                        compared_params += 1
            
            return total_distance / compared_params if compared_params > 0 else 1.0
            
        except Exception as e:
            logger.warning(f"Error calculating parameter distance: {e}")
            return 1.0

    def calculate_robustness_score(self, walkforward) -> Dict[str, Any]:
        """Calculate comprehensive robustness score"""
        try:
            windows = list(walkforward.windows.all())
            completed_windows = [w for w in windows if w.status == 'COMPLETED']
            
            if len(completed_windows) < 2:
                return {
                    'robustness_score': Decimal('0.00'),
                    'consistency_score': Decimal('0.00'),
                    'parameter_stability': Decimal('0.00'),
                    'is_robust': False,
                    'robustness_notes': 'Insufficient completed windows'
                }
            
            # 1. Performance Consistency (40%)
            oos_roi_values = [float(w.out_sample_roi) for w in completed_windows]
            positive_windows = sum(1 for roi in oos_roi_values if roi > 0)
            consistency_score = (positive_windows / len(oos_roi_values)) * 100
            
            # 2. Performance Degradation (30%)
            degradation_scores = []
            for window in completed_windows:
                if float(window.in_sample_roi) != 0:
                    degradation = (float(window.in_sample_roi) - float(window.out_sample_roi)) / abs(float(window.in_sample_roi))
                    degradation_scores.append(max(0, 100 - (abs(degradation) * 100)))
                else:
                    degradation_scores.append(0)
            
            degradation_score = sum(degradation_scores) / len(degradation_scores) if degradation_scores else 0
            
            # 3. Parameter Stability (20%)
            param_stability = float(self.calculate_parameter_stability(completed_windows))
            
            # 4. Trade Consistency (10%)
            trade_counts = [w.out_sample_total_trades for w in completed_windows]
            if trade_counts:
                trade_cv = np.std(trade_counts) / np.mean(trade_counts)  # Coefficient of variation
                trade_consistency = max(0, 100 - (trade_cv * 50))  # Normalize to 0-100
            else:
                trade_consistency = 0
            
            # Composite robustness score
            robustness_score = (
                consistency_score * 0.4 +
                degradation_score * 0.3 +
                param_stability * 0.2 +
                trade_consistency * 0.1
            )
            
            # Determine if robust
            is_robust = (
                robustness_score >= 60 and
                consistency_score >= 50 and
                degradation_score >= 50 and
                param_stability >= 50
            )
            
            notes = []
            if robustness_score < 60:
                notes.append("Overall robustness score too low")
            if consistency_score < 50:
                notes.append("Inconsistent performance across windows")
            if degradation_score < 50:
                notes.append("High performance degradation")
            if param_stability < 50:
                notes.append("Parameters too unstable")
            
            return {
                'robustness_score': Decimal(str(round(robustness_score, 2))),
                'consistency_score': Decimal(str(round(consistency_score, 2))),
                'parameter_stability': Decimal(str(round(param_stability, 2))),
                'degradation_score': Decimal(str(round(degradation_score, 2))),
                'is_robust': is_robust,
                'robustness_notes': '; '.join(notes) if notes else 'Strategy appears robust'
            }
            
        except Exception as e:
            logger.error(f"Error calculating robustness score: {e}")
            return {
                'robustness_score': Decimal('0.00'),
                'consistency_score': Decimal('0.00'),
                'parameter_stability': Decimal('0.00'),
                'is_robust': False,
                'robustness_notes': f'Error: {str(e)}'
            }


@shared_task(bind=True, max_retries=1)
def run_walkforward_optimization_async(self, walkforward_id: int):
    """
    OPTIMIZED Walk-Forward Optimization Task
    Enhanced with robustness metrics, regime detection, and multi-objective optimization.
    """
    from signals.models_walkforward import WalkForwardOptimization, WalkForwardWindow
    from scanner.services.walkforward_engine import WalkForwardEngine
    from scanner.services.parameter_optimizer import ParameterOptimizer
    from scanner.services.backtest_engine import BacktestEngine
    from scanner.services.historical_data_fetcher import HistoricalDataFetcher

    try:
        # Load configuration
        walkforward = WalkForwardOptimization.objects.get(id=walkforward_id)
        walkforward.status = 'RUNNING'
        walkforward.started_at = datetime.now()
        walkforward.save()

        logger.info(f"🚀 Starting OPTIMIZED walk-forward: {walkforward.name} (ID: {walkforward_id})")

        # Initialize engines
        wf_engine = WalkForwardEngine()
        wf_optimizer = WalkForwardOptimizer()

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

        logger.info(f"📊 Generated {len(windows)} windows for analysis")

        # Create window records
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

        # Process windows with enhanced optimization
        completed_windows = []
        
        for idx, (window_config, window_record) in enumerate(zip(windows, window_records)):
            logger.info(f"🔄 Processing window {window_config['window_number']}/{len(windows)}")
            
            try:
                # Set up async loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # === OPTIMIZATION PHASE ===
                window_record.status = 'OPTIMIZING'
                window_record.save()

                logger.info(f"  🎯 Optimizing parameters on training data...")
                
                # Fetch training data
                historical_fetcher = HistoricalDataFetcher()
                symbols_data_train = loop.run_until_complete(
                    historical_fetcher.fetch_multiple_symbols(
                        walkforward.symbols,
                        walkforward.timeframe,
                        window_config['training_start'],
                        window_config['training_end']
                    )
                )

                # Classify market regime
                if symbols_data_train and walkforward.symbols:
                    first_symbol = walkforward.symbols[0]
                    if first_symbol in symbols_data_train:
                        market_regime = wf_optimizer.classify_market_regime(
                            symbols_data_train[first_symbol]
                        )
                        window_record.market_regime = market_regime
                        logger.info(f"  📈 Market regime: {market_regime}")

                # Run parameter optimization with enhanced scoring
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
                        max_combinations=50,
                        scoring_function='composite'  # Use composite scoring
                    )
                )

                # Find best valid result
                best_result = None
                best_composite_score = Decimal('-100.0')
                
                for result in optimization_results:
                    is_valid, validation_msg = wf_optimizer.validate_optimization_result(result)
                    composite_score = wf_optimizer.calculate_composite_score(result)
                    
                    if is_valid and composite_score > best_composite_score:
                        best_result = result
                        best_composite_score = composite_score
                        logger.info(f"    ✅ Valid candidate: ROI={result['roi']:.2f}%, Score={composite_score:.4f}")

                if not best_result:
                    logger.warning(f"    ⚠️ No valid optimization results found for window {window_config['window_number']}")
                    window_record.status = 'FAILED'
                    window_record.error_message = "No valid parameter sets found"
                    window_record.save()
                    continue

                best_params = best_result['params']
                
                # Store in-sample results
                window_record.best_params = best_params
                window_record.in_sample_total_trades = best_result['total_trades']
                window_record.in_sample_win_rate = Decimal(str(best_result['win_rate']))
                window_record.in_sample_roi = Decimal(str(best_result['roi']))
                window_record.in_sample_sharpe = Decimal(str(best_result.get('sharpe_ratio', 0))) if best_result.get('sharpe_ratio') else None
                window_record.in_sample_max_drawdown = Decimal(str(best_result.get('max_drawdown', 0)))
                window_record.in_sample_profit_factor = Decimal(str(best_result.get('profit_factor', 0)))
                window_record.composite_score = best_composite_score
                
                logger.info(f"    📊 In-sample: {best_result['total_trades']} trades, "
                          f"{best_result['win_rate']:.2f}% WR, {best_result['roi']:.2f}% ROI, "
                          f"Score: {best_composite_score:.4f}")

                # === TESTING PHASE ===
                window_record.status = 'TESTING'
                window_record.save()

                logger.info(f"  🔬 Testing parameters on out-of-sample data...")

                # Fetch testing data
                symbols_data_test = loop.run_until_complete(
                    historical_fetcher.fetch_multiple_symbols(
                        walkforward.symbols,
                        walkforward.timeframe,
                        window_config['testing_start'],
                        window_config['testing_end']
                    )
                )

                # Run backtest with best parameters
                backtest_engine = BacktestEngine(
                    initial_capital=float(walkforward.initial_capital),
                    position_size=float(walkforward.position_size),
                    strategy_params=best_params
                )

                # Generate signals and run backtest
                signal_config = _optimized_dict_to_signal_config(best_params)
                engine = SignalDetectionEngine(signal_config)
                signals = []

                for symbol, klines in symbols_data_test.items():
                    engine.update_candles(symbol, klines)
                    for candle in klines:
                        signal = engine.analyze_candle(symbol, candle)
                        if signal:
                            signals.append(signal)

                test_results = backtest_engine.run_backtest(symbols_data_test, signals)

                # Store out-of-sample results
                window_record.out_sample_total_trades = test_results['total_trades']
                window_record.out_sample_win_rate = Decimal(str(test_results['win_rate']))
                window_record.out_sample_roi = Decimal(str(test_results['roi']))
                window_record.out_sample_sharpe = Decimal(str(test_results.get('sharpe_ratio', 0))) if test_results.get('sharpe_ratio') else None
                window_record.out_sample_max_drawdown = Decimal(str(test_results.get('max_drawdown', 0)))
                window_record.out_sample_profit_factor = Decimal(str(test_results.get('profit_factor', 0)))

                # Calculate performance drop
                in_roi = float(window_record.in_sample_roi)
                out_roi = float(window_record.out_sample_roi)
                if in_roi != 0:
                    perf_drop = ((in_roi - out_roi) / abs(in_roi)) * 100
                    window_record.performance_drop_pct = Decimal(str(round(perf_drop, 2)))

                window_record.status = 'COMPLETED'
                window_record.save()

                completed_windows.append(window_record)
                
                logger.info(f"    📊 Out-of-sample: {test_results['total_trades']} trades, "
                          f"{test_results['win_rate']:.2f}% WR, {test_results['roi']:.2f}% ROI")
                if window_record.performance_drop_pct:
                    logger.info(f"    📉 Performance drop: {window_record.performance_drop_pct:.2f}%")

                # Update progress
                walkforward.completed_windows = idx + 1
                walkforward.save()

                loop.close()

            except Exception as e:
                logger.error(f"❌ Error processing window {window_config['window_number']}: {e}", exc_info=True)
                window_record.status = 'FAILED'
                window_record.error_message = str(e)
                window_record.save()
                continue

        # === AGGREGATE RESULTS WITH ROBUSTNESS ANALYSIS ===
        logger.info("📈 Aggregating results with robustness analysis...")

        # Calculate aggregate metrics
        if completed_windows:
            aggregate_metrics = wf_engine.calculate_aggregate_metrics(completed_windows)
            
            # Calculate comprehensive robustness score
            robustness_results = wf_optimizer.calculate_robustness_score(walkforward)
            
            # Update walk-forward with all results
            walkforward.avg_in_sample_win_rate = aggregate_metrics.get('avg_in_sample_win_rate', Decimal('0.00'))
            walkforward.avg_out_sample_win_rate = aggregate_metrics.get('avg_out_sample_win_rate', Decimal('0.00'))
            walkforward.avg_in_sample_roi = aggregate_metrics.get('avg_in_sample_roi', Decimal('0.00'))
            walkforward.avg_out_sample_roi = aggregate_metrics.get('avg_out_sample_roi', Decimal('0.00'))
            walkforward.performance_degradation = aggregate_metrics.get('performance_degradation', Decimal('0.00'))
            
            # Enhanced robustness metrics
            walkforward.robustness_score = robustness_results['robustness_score']
            walkforward.consistency_score = robustness_results['consistency_score']
            walkforward.parameter_stability = robustness_results['parameter_stability']
            walkforward.is_robust = robustness_results['is_robust']
            walkforward.robustness_notes = robustness_results['robustness_notes']
            
            # Store market regime performance
            regime_performance = {}
            for regime in ['HIGH_VOL_TREND', 'HIGH_VOL_RANGE', 'LOW_VOL_TREND', 'LOW_VOL_RANGE']:
                regime_windows = [w for w in completed_windows if getattr(w, 'market_regime', None) == regime]
                if regime_windows:
                    avg_roi = sum(float(w.out_sample_roi) for w in regime_windows) / len(regime_windows)
                    regime_performance[regime] = {
                        'window_count': len(regime_windows),
                        'avg_roi': avg_roi,
                        'avg_win_rate': sum(float(w.out_sample_win_rate) for w in regime_windows) / len(regime_windows)
                    }
            
            walkforward.market_regime_performance = regime_performance

        walkforward.status = 'COMPLETED'
        walkforward.completed_at = datetime.now()
        walkforward.save()

        # Final summary
        logger.info(f"✅ Walk-forward optimization COMPLETED!")
        logger.info(f"   Robustness Score: {walkforward.robustness_score:.1f}/100")
        logger.info(f"   Consistency Score: {walkforward.consistency_score:.1f}/100") 
        logger.info(f"   Parameter Stability: {walkforward.parameter_stability:.1f}/100")
        logger.info(f"   Out-of-Sample ROI: {walkforward.avg_out_sample_roi:.2f}%")
        logger.info(f"   Strategy Robust: {'✅ YES' if walkforward.is_robust else '❌ NO'}")

        return {
            'walkforward_id': walkforward_id,
            'status': 'COMPLETED',
            'is_robust': walkforward.is_robust,
            'robustness_score': float(walkforward.robustness_score),
            'avg_out_sample_roi': float(walkforward.avg_out_sample_roi),
            'consistency_score': float(walkforward.consistency_score),
        }

    except Exception as e:
        logger.error(f"💥 Critical error in walk-forward optimization {walkforward_id}: {e}", exc_info=True)

        try:
            walkforward = WalkForwardOptimization.objects.get(id=walkforward_id)
            walkforward.status = 'FAILED'
            walkforward.error_message = str(e)
            walkforward.completed_at = datetime.now()
            walkforward.save()
        except Exception as save_error:
            logger.error(f"Failed to update walkforward status: {save_error}")

        raise self.retry(exc=e, countdown=60)


def _optimized_dict_to_signal_config(params: dict):
    """Optimized parameter conversion with proper RSI range handling"""
    from scanner.strategies.signal_engine import SignalConfig

    return SignalConfig(
        # LONG signals (oversold bounce in uptrend)
        long_rsi_min=params.get('long_rsi_min', 23.0),
        long_rsi_max=params.get('long_rsi_max', 33.0),
        long_adx_min=params.get('long_adx_min', 25.0),
        long_volume_multiplier=params.get('volume_multiplier', 1.2),

        # SHORT signals (overbought rejection in downtrend)  
        short_rsi_min=params.get('short_rsi_min', 67.0),
        short_rsi_max=params.get('short_rsi_max', 77.0),
        short_adx_min=params.get('short_adx_min', 25.0),
        short_volume_multiplier=params.get('volume_multiplier', 1.2),

        # Risk management
        sl_atr_multiplier=params.get('sl_atr_multiplier', 2.5),
        tp_atr_multiplier=params.get('tp_atr_multiplier', 7.0),

        # Signal quality
        min_confidence=params.get('min_confidence', 0.7),
        max_candles_cache=200,
    )