"""
Monte Carlo Simulation Engine

Performs statistical robustness testing by running multiple simulations
with randomized parameters and analyzing the distribution of outcomes.

Key Features:
- Parameter randomization
- Statistical analysis (mean, median, std dev, confidence intervals)
- Probability calculations
- Risk metrics (VaR, drawdown distribution)
- Robustness scoring
"""

import random
import statistics
from decimal import Decimal
from typing import Dict, List, Tuple, Any
import numpy as np


class MonteCarloEngine:
    """Engine for running Monte Carlo simulations and statistical analysis."""

    def __init__(self):
        """Initialize Monte Carlo engine."""
        self.random = random.Random()

    def randomize_parameters(
        self,
        base_params: Dict[str, Any],
        randomization_config: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        Generate randomized parameters for a single simulation run.

        Args:
            base_params: Base strategy parameters
            randomization_config: Ranges for randomization
                e.g., {'rsi_oversold': {'min': 25, 'max': 35, 'type': 'uniform'}}

        Returns:
            Dictionary of randomized parameters
        """
        randomized = base_params.copy()

        for param_name, config in randomization_config.items():
            if param_name not in base_params:
                continue

            distribution_type = config.get('type', 'uniform')
            min_val = config.get('min')
            max_val = config.get('max')

            if min_val is None or max_val is None:
                continue

            if distribution_type == 'uniform':
                # Uniform distribution
                randomized[param_name] = self.random.uniform(min_val, max_val)

            elif distribution_type == 'normal':
                # Normal distribution (mean = base value, std = specified)
                base_val = base_params[param_name]
                std_dev = config.get('std', (max_val - min_val) / 4)
                value = self.random.gauss(base_val, std_dev)
                # Clamp to min/max
                randomized[param_name] = max(min_val, min(max_val, value))

            elif distribution_type == 'discrete':
                # Discrete uniform (integers only)
                randomized[param_name] = self.random.randint(int(min_val), int(max_val))

        return randomized

    def calculate_statistics(self, values: List[float]) -> Dict[str, Decimal]:
        """
        Calculate statistical metrics for a list of values.

        Args:
            values: List of numeric values

        Returns:
            Dictionary with statistical metrics
        """
        if not values:
            return {
                'mean': Decimal('0.00'),
                'median': Decimal('0.00'),
                'std_dev': Decimal('0.00'),
                'variance': Decimal('0.00'),
                'min': Decimal('0.00'),
                'max': Decimal('0.00'),
            }

        values_sorted = sorted(values)

        return {
            'mean': Decimal(str(round(statistics.mean(values), 2))),
            'median': Decimal(str(round(statistics.median(values), 2))),
            'std_dev': Decimal(str(round(statistics.stdev(values) if len(values) > 1 else 0, 2))),
            'variance': Decimal(str(round(statistics.variance(values) if len(values) > 1 else 0, 2))),
            'min': Decimal(str(round(min(values), 2))),
            'max': Decimal(str(round(max(values), 2))),
        }

    def calculate_confidence_intervals(
        self,
        values: List[float],
        confidence_level: float = 0.95
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate confidence interval for given confidence level.

        Args:
            values: List of numeric values
            confidence_level: Confidence level (e.g., 0.95 for 95%)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if not values or len(values) < 2:
            return Decimal('0.00'), Decimal('0.00')

        values_sorted = sorted(values)
        n = len(values_sorted)

        # Calculate percentile indices
        alpha = 1 - confidence_level
        lower_idx = int(n * (alpha / 2))
        upper_idx = int(n * (1 - alpha / 2))

        # Ensure indices are within bounds
        lower_idx = max(0, min(lower_idx, n - 1))
        upper_idx = max(0, min(upper_idx, n - 1))

        lower_bound = Decimal(str(round(values_sorted[lower_idx], 2)))
        upper_bound = Decimal(str(round(values_sorted[upper_idx], 2)))

        return lower_bound, upper_bound

    def calculate_percentiles(self, values: List[float]) -> Dict[str, Decimal]:
        """
        Calculate key percentiles for a distribution.

        Args:
            values: List of numeric values

        Returns:
            Dictionary with percentile values
        """
        if not values:
            return {
                'p5': Decimal('0.00'),
                'p25': Decimal('0.00'),
                'p50': Decimal('0.00'),
                'p75': Decimal('0.00'),
                'p95': Decimal('0.00'),
            }

        values_sorted = sorted(values)
        n = len(values_sorted)

        def get_percentile(p: float) -> float:
            idx = int(n * p / 100)
            idx = max(0, min(idx, n - 1))
            return values_sorted[idx]

        return {
            'p5': Decimal(str(round(get_percentile(5), 2))),
            'p25': Decimal(str(round(get_percentile(25), 2))),
            'p50': Decimal(str(round(get_percentile(50), 2))),
            'p75': Decimal(str(round(get_percentile(75), 2))),
            'p95': Decimal(str(round(get_percentile(95), 2))),
        }

    def calculate_value_at_risk(
        self,
        returns: List[float],
        confidence_level: float = 0.95
    ) -> Decimal:
        """
        Calculate Value at Risk (VaR).

        VaR represents the maximum loss expected at a given confidence level.

        Args:
            returns: List of return values (ROI percentages)
            confidence_level: Confidence level (e.g., 0.95 for 95%)

        Returns:
            VaR value (positive number representing potential loss)
        """
        if not returns:
            return Decimal('0.00')

        returns_sorted = sorted(returns)
        n = len(returns_sorted)

        # VaR is the percentile at (1 - confidence_level)
        var_idx = int(n * (1 - confidence_level))
        var_idx = max(0, min(var_idx, n - 1))

        var_value = returns_sorted[var_idx]

        # VaR is reported as a positive number representing potential loss
        return Decimal(str(round(abs(var_value) if var_value < 0 else 0, 2)))

    def calculate_probability_of_profit(self, returns: List[float]) -> Decimal:
        """
        Calculate probability of profit.

        Args:
            returns: List of return values (ROI percentages)

        Returns:
            Percentage of simulations with positive returns
        """
        if not returns:
            return Decimal('0.00')

        profitable = sum(1 for r in returns if r > 0)
        probability = (profitable / len(returns)) * 100

        return Decimal(str(round(probability, 2)))

    def calculate_probability_of_loss(self, returns: List[float]) -> Decimal:
        """
        Calculate probability of loss.

        Args:
            returns: List of return values (ROI percentages)

        Returns:
            Percentage of simulations with negative returns
        """
        if not returns:
            return Decimal('0.00')

        losing = sum(1 for r in returns if r < 0)
        probability = (losing / len(returns)) * 100

        return Decimal(str(round(probability, 2)))

    def generate_histogram_data(
        self,
        values: List[float],
        num_bins: int = 30
    ) -> Tuple[List[float], List[int]]:
        """
        Generate histogram data for visualization.

        Args:
            values: List of numeric values
            num_bins: Number of bins for histogram

        Returns:
            Tuple of (bin_edges, frequencies)
        """
        if not values:
            return [], []

        # Use numpy for histogram calculation
        values_array = np.array(values)
        frequencies, bin_edges = np.histogram(values_array, bins=num_bins)

        return bin_edges.tolist(), frequencies.tolist()

    def assess_statistical_robustness(
        self,
        mean_return: float,
        std_deviation: float,
        probability_of_profit: float,
        var_95: float,
        mean_sharpe: float,
    ) -> Tuple[bool, Decimal, str]:
        """
        Assess whether the strategy is statistically robust.

        Criteria:
        1. Mean return > 0 (positive expected value)
        2. Probability of profit > 60%
        3. Sharpe ratio > 1.0 (good risk-adjusted returns)
        4. VaR at 95% < 20% (limited downside risk)
        5. Coefficient of variation < 2.0 (consistent returns)

        Args:
            mean_return: Mean ROI across simulations
            std_deviation: Standard deviation of returns
            probability_of_profit: Percentage of profitable simulations
            var_95: Value at Risk at 95% confidence
            mean_sharpe: Mean Sharpe ratio

        Returns:
            Tuple of (is_robust, robustness_score, explanation)
        """
        is_robust = True
        reasons = []
        score_components = []

        # Criterion 1: Positive expected value (30 points)
        if mean_return > 0:
            score_components.append(30)
            reasons.append(f"✅ Positive expected return ({mean_return:.2f}%)")
        else:
            is_robust = False
            score_components.append(0)
            reasons.append(f"❌ Negative expected return ({mean_return:.2f}%)")

        # Criterion 2: High probability of profit (25 points)
        if probability_of_profit >= 70:
            score_components.append(25)
            reasons.append(f"✅ High probability of profit ({probability_of_profit:.1f}%)")
        elif probability_of_profit >= 60:
            score_components.append(15)
            reasons.append(f"⚠️ Moderate probability of profit ({probability_of_profit:.1f}%)")
        else:
            is_robust = False
            score_components.append(0)
            reasons.append(f"❌ Low probability of profit ({probability_of_profit:.1f}%)")

        # Criterion 3: Good risk-adjusted returns (25 points)
        if mean_sharpe >= 1.5:
            score_components.append(25)
            reasons.append(f"✅ Excellent Sharpe ratio ({mean_sharpe:.2f})")
        elif mean_sharpe >= 1.0:
            score_components.append(15)
            reasons.append(f"⚠️ Good Sharpe ratio ({mean_sharpe:.2f})")
        else:
            is_robust = False
            score_components.append(0)
            reasons.append(f"❌ Poor Sharpe ratio ({mean_sharpe:.2f})")

        # Criterion 4: Limited downside risk (20 points)
        if var_95 < 10:
            score_components.append(20)
            reasons.append(f"✅ Low downside risk (VaR: {var_95:.2f}%)")
        elif var_95 < 20:
            score_components.append(10)
            reasons.append(f"⚠️ Moderate downside risk (VaR: {var_95:.2f}%)")
        else:
            is_robust = False
            score_components.append(0)
            reasons.append(f"❌ High downside risk (VaR: {var_95:.2f}%)")

        # Criterion 5: Consistency (coefficient of variation)
        if std_deviation > 0 and mean_return != 0:
            cv = abs(std_deviation / mean_return)
            if cv < 1.0:
                score_components.append(20)
                reasons.append(f"✅ Consistent returns (CV: {cv:.2f})")
            elif cv < 2.0:
                score_components.append(10)
                reasons.append(f"⚠️ Moderate consistency (CV: {cv:.2f})")
            else:
                score_components.append(0)
                reasons.append(f"❌ Inconsistent returns (CV: {cv:.2f})")
        else:
            score_components.append(0)
            reasons.append("⚠️ Cannot calculate consistency")

        # Calculate total score
        total_score = sum(score_components)
        robustness_score = Decimal(str(total_score))

        # Overall assessment
        if is_robust and total_score >= 80:
            reasons.insert(0, "🎯 **STATISTICALLY ROBUST** - Strategy shows strong statistical properties")
        elif total_score >= 60:
            reasons.insert(0, "⚠️ **MODERATELY ROBUST** - Strategy shows acceptable statistical properties")
        else:
            reasons.insert(0, "❌ **NOT ROBUST** - Strategy fails statistical robustness criteria")

        reasons_text = "\n".join(reasons)

        return is_robust and total_score >= 80, robustness_score, reasons_text

    def aggregate_simulation_results(
        self,
        simulation_runs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate results from multiple simulation runs.

        Args:
            simulation_runs: List of dictionaries with simulation results

        Returns:
            Dictionary with aggregated statistics
        """
        if not simulation_runs:
            return {}

        # Extract metrics
        rois = [float(run.get('roi', 0)) for run in simulation_runs]
        drawdowns = [float(run.get('max_drawdown', 0)) for run in simulation_runs]
        win_rates = [float(run.get('win_rate', 0)) for run in simulation_runs]
        sharpe_ratios = [float(run.get('sharpe_ratio', 0)) for run in simulation_runs]
        profit_factors = [float(run.get('profit_factor', 0)) for run in simulation_runs]
        total_trades = [int(run.get('total_trades', 0)) for run in simulation_runs]

        # Calculate statistics for each metric
        roi_stats = self.calculate_statistics(rois)
        drawdown_stats = self.calculate_statistics(drawdowns)
        win_rate_stats = self.calculate_statistics(win_rates)
        sharpe_stats = self.calculate_statistics(sharpe_ratios)

        # Confidence intervals
        ci_95_lower, ci_95_upper = self.calculate_confidence_intervals(rois, 0.95)
        ci_99_lower, ci_99_upper = self.calculate_confidence_intervals(rois, 0.99)

        # Risk metrics
        var_95 = self.calculate_value_at_risk(rois, 0.95)
        var_99 = self.calculate_value_at_risk(rois, 0.99)

        # Probability metrics
        prob_profit = self.calculate_probability_of_profit(rois)
        prob_loss = self.calculate_probability_of_loss(rois)

        # Robustness assessment
        is_robust, robustness_score, robustness_reasons = self.assess_statistical_robustness(
            mean_return=float(roi_stats['mean']),
            std_deviation=float(roi_stats['std_dev']),
            probability_of_profit=float(prob_profit),
            var_95=float(var_95),
            mean_sharpe=float(sharpe_stats['mean']),
        )

        return {
            # Central tendency
            'mean_return': roi_stats['mean'],
            'median_return': roi_stats['median'],

            # Dispersion
            'std_deviation': roi_stats['std_dev'],
            'variance': roi_stats['variance'],

            # Confidence intervals
            'confidence_95_lower': ci_95_lower,
            'confidence_95_upper': ci_95_upper,
            'confidence_99_lower': ci_99_lower,
            'confidence_99_upper': ci_99_upper,

            # Probability
            'probability_of_profit': prob_profit,
            'probability_of_loss': prob_loss,

            # Risk
            'value_at_risk_95': var_95,
            'value_at_risk_99': var_99,

            # Extremes
            'best_case_return': roi_stats['max'],
            'worst_case_return': roi_stats['min'],

            # Drawdown
            'mean_max_drawdown': drawdown_stats['mean'],
            'worst_case_drawdown': drawdown_stats['max'],
            'best_case_drawdown': drawdown_stats['min'],

            # Performance metrics
            'mean_sharpe_ratio': sharpe_stats['mean'],
            'median_sharpe_ratio': sharpe_stats['median'],
            'mean_win_rate': win_rate_stats['mean'],
            'median_win_rate': win_rate_stats['median'],

            # Robustness
            'is_statistically_robust': is_robust,
            'robustness_score': robustness_score,
            'robustness_reasons': robustness_reasons,
        }
