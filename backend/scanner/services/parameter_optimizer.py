"""
Parameter Optimization System
Automatically tests multiple parameter combinations to find optimal strategy settings.
"""
import logging
import asyncio
from typing import List, Dict, Tuple
from itertools import product
from datetime import datetime
from decimal import Decimal
import numpy as np

from scanner.services.historical_data_fetcher import historical_data_fetcher
from scanner.services.backtest_engine import BacktestEngine
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """
    Optimizes strategy parameters using grid search or random search.
    Tests multiple combinations and ranks by performance.
    """

    def __init__(self):
        self.results = []

    async def optimize_parameters(
        self,
        symbols: List[str],
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        parameter_ranges: Dict[str, List],
        initial_capital: Decimal = Decimal('10000'),
        position_size: Decimal = Decimal('100'),
        search_method: str = 'grid',
        max_combinations: int = 100
    ) -> List[Dict]:
        """
        Run parameter optimization.

        Args:
            symbols: List of symbols to test
            timeframe: Timeframe to use
            start_date: Start of backtest period
            end_date: End of backtest period
            parameter_ranges: Dict of parameter names to list of values
            initial_capital: Starting capital
            position_size: Position size per trade
            search_method: 'grid' or 'random'
            max_combinations: Maximum combinations to test (for random search)

        Returns:
            List of results sorted by performance
        """
        logger.info(f"🔍 Starting parameter optimization for {symbols}")
        logger.info(f"Parameter ranges: {parameter_ranges}")

        # Generate parameter combinations
        if search_method == 'grid':
            combinations = self._generate_grid_combinations(parameter_ranges)
        else:
            combinations = self._generate_random_combinations(parameter_ranges, max_combinations)

        logger.info(f"Testing {len(combinations)} parameter combinations...")

        # Fetch historical data once (reuse for all tests)
        logger.info(f"Fetching historical data from {start_date} to {end_date}...")
        symbols_data = await historical_data_fetcher.fetch_multiple_symbols(
            symbols,
            timeframe,
            start_date,
            end_date
        )

        # Test each combination
        results = []
        for idx, params in enumerate(combinations, 1):
            try:
                logger.info(f"Testing combination {idx}/{len(combinations)}: {params}")

                # Run backtest with these parameters
                result = await self._run_single_backtest(
                    params,
                    symbols_data,
                    timeframe,
                    initial_capital,
                    position_size
                )

                result['params'] = params
                result['combination_id'] = idx
                results.append(result)

                logger.info(
                    f"  Result: Win Rate: {result['win_rate']:.2f}%, "
                    f"ROI: {result['roi']:.2f}%, Score: {result['optimization_score']:.4f}"
                )

            except Exception as e:
                logger.error(f"Error testing combination {idx}: {e}", exc_info=True)

        # Sort by optimization score
        results.sort(key=lambda x: x['optimization_score'], reverse=True)

        logger.info(f"✅ Optimization complete! Best score: {results[0]['optimization_score']:.4f}")

        self.results = results
        return results

    def _generate_grid_combinations(self, parameter_ranges: Dict[str, List]) -> List[Dict]:
        """
        Generate all possible combinations (grid search).

        Args:
            parameter_ranges: Dict mapping param name to list of values

        Returns:
            List of parameter dictionaries
        """
        param_names = list(parameter_ranges.keys())
        param_values = [parameter_ranges[name] for name in param_names]

        # Generate cartesian product
        combinations = []
        for values in product(*param_values):
            combo = dict(zip(param_names, values))
            combinations.append(combo)

        return combinations

    def _generate_random_combinations(
        self,
        parameter_ranges: Dict[str, List],
        max_combinations: int
    ) -> List[Dict]:
        """
        Generate random parameter combinations (random search).

        Args:
            parameter_ranges: Dict mapping param name to list of values
            max_combinations: Max number of combinations

        Returns:
            List of parameter dictionaries
        """
        import random

        combinations = []
        for _ in range(max_combinations):
            combo = {}
            for param_name, param_values in parameter_ranges.items():
                combo[param_name] = random.choice(param_values)
            combinations.append(combo)

        return combinations

    async def _run_single_backtest(
        self,
        params: Dict,
        symbols_data: Dict[str, List[Dict]],
        timeframe: str,
        initial_capital: Decimal,
        position_size: Decimal
    ) -> Dict:
        """
        Run a single backtest with given parameters.

        Args:
            params: Strategy parameters
            symbols_data: Historical OHLCV data
            timeframe: Timeframe
            initial_capital: Starting capital
            position_size: Position size per trade

        Returns:
            Dictionary with backtest results and metrics
        """
        # Create signal config from parameters
        signal_config = self._params_to_signal_config(params)

        # Initialize signal detection engine
        engine = SignalDetectionEngine(signal_config)

        # Generate signals on historical data
        signals = []
        for symbol, klines in symbols_data.items():
            if not klines:
                continue

            # Update engine cache with historical data
            engine.update_candles(symbol, klines)

            # Process each candle to detect signals
            for candle in klines:
                result = engine.process_symbol(symbol, timeframe)
                if result and result.get('action') == 'created':
                    signal_data = result['signal']
                    signals.append({
                        'symbol': symbol,
                        'timestamp': candle['timestamp'],
                        'direction': signal_data['direction'],
                        'entry': signal_data['entry'],
                        'tp': signal_data['tp'],
                        'sl': signal_data['sl'],
                        'confidence': signal_data.get('confidence', 0.7),
                        'indicators': signal_data.get('indicators', {})
                    })

        logger.debug(f"Generated {len(signals)} signals for testing")

        # Run backtest with these signals
        backtest_engine = BacktestEngine(
            initial_capital=initial_capital,
            position_size=position_size,
            strategy_params=params
        )

        results = backtest_engine.run_backtest(symbols_data, signals)

        # Calculate optimization score
        optimization_score = self._calculate_optimization_score(results)
        results['optimization_score'] = optimization_score

        return results

    def _params_to_signal_config(self, params: Dict) -> SignalConfig:
        """
        Convert parameter dictionary to SignalConfig object.

        Args:
            params: Parameter dictionary

        Returns:
            SignalConfig instance
        """
        config = SignalConfig()

        # Map parameters to config attributes
        param_mapping = {
            'long_rsi_min': 'long_rsi_min',
            'long_rsi_max': 'long_rsi_max',
            'short_rsi_min': 'short_rsi_min',
            'short_rsi_max': 'short_rsi_max',
            'long_adx_min': 'long_adx_min',
            'short_adx_min': 'short_adx_min',
            'sl_atr_multiplier': 'sl_atr_multiplier',
            'tp_atr_multiplier': 'tp_atr_multiplier',
            'min_confidence': 'min_confidence',
            'macd_weight': 'macd_weight',
            'rsi_weight': 'rsi_weight',
            'price_ema_weight': 'price_ema_weight',
            'adx_weight': 'adx_weight',
        }

        for param_key, config_key in param_mapping.items():
            if param_key in params:
                setattr(config, config_key, params[param_key])

        return config

    def _calculate_optimization_score(self, results: Dict) -> Decimal:
        """
        Calculate composite optimization score.

        Weights:
        - Win Rate: 35%
        - ROI: 30%
        - Sharpe Ratio: 20%
        - Profit Factor: 15%

        Args:
            results: Backtest results

        Returns:
            Optimization score (0-100)
        """
        if results['total_trades'] == 0:
            return Decimal('0')

        # Normalize metrics (0-100 scale)
        win_rate_norm = min(float(results['win_rate']), 100)  # Already 0-100

        # ROI normalization (assume 100% ROI = 100 points, can be higher)
        roi_norm = min(max(float(results['roi']) * 1.0, 0), 100)

        # Sharpe ratio normalization (3.0 = excellent = 100 points)
        sharpe_norm = min(max(float(results.get('sharpe_ratio', 0)) * 33.33, 0), 100)

        # Profit factor normalization (3.0 = excellent = 100 points)
        profit_factor_norm = min(max(float(results.get('profit_factor', 0)) * 33.33, 0), 100)

        # Weighted average
        score = (
            win_rate_norm * 0.35 +
            roi_norm * 0.30 +
            sharpe_norm * 0.20 +
            profit_factor_norm * 0.15
        )

        # Penalty for low trade count (need sufficient data)
        if results['total_trades'] < 30:
            penalty = 1 - (results['total_trades'] / 30) * 0.2  # Up to 20% penalty
            score *= penalty

        return Decimal(str(round(score, 4)))

    def get_best_parameters(self, top_n: int = 5) -> List[Dict]:
        """
        Get top N best parameter combinations.

        Args:
            top_n: Number of top results to return

        Returns:
            List of top performing parameter sets
        """
        return self.results[:top_n]

    def get_parameter_analysis(self, param_name: str) -> Dict:
        """
        Analyze how a specific parameter affects performance.

        Args:
            param_name: Name of parameter to analyze

        Returns:
            Dictionary with analysis results
        """
        if not self.results:
            return {}

        param_values = {}

        for result in self.results:
            params = result['params']
            if param_name not in params:
                continue

            value = params[param_name]
            if value not in param_values:
                param_values[value] = {
                    'count': 0,
                    'avg_score': 0,
                    'avg_win_rate': 0,
                    'avg_roi': 0,
                    'scores': []
                }

            param_values[value]['count'] += 1
            param_values[value]['scores'].append(float(result['optimization_score']))
            param_values[value]['avg_win_rate'] += float(result['win_rate'])
            param_values[value]['avg_roi'] += float(result['roi'])

        # Calculate averages
        for value, data in param_values.items():
            count = data['count']
            data['avg_score'] = np.mean(data['scores'])
            data['avg_win_rate'] /= count
            data['avg_roi'] /= count
            data['std_score'] = np.std(data['scores'])

        # Find optimal value
        best_value = max(param_values.items(), key=lambda x: x[1]['avg_score'])

        return {
            'parameter': param_name,
            'values_tested': param_values,
            'best_value': best_value[0],
            'best_avg_score': best_value[1]['avg_score'],
            'best_avg_win_rate': best_value[1]['avg_win_rate'],
            'best_avg_roi': best_value[1]['avg_roi']
        }


# Singleton instance
parameter_optimizer = ParameterOptimizer()
