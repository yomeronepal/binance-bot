"""
Walk-Forward Optimization Engine
Implements rolling window optimization and testing for strategy robustness validation.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
import logging
import statistics

logger = logging.getLogger(__name__)


class WalkForwardEngine:
    """
    Engine for performing walk-forward optimization analysis.

    Process:
    1. Split time period into overlapping or sequential windows
    2. For each window:
       a. Optimize parameters on training data (in-sample)
       b. Test optimized parameters on following test period (out-of-sample)
    3. Aggregate results to assess strategy robustness
    """

    def __init__(self):
        self.logger = logger

    def generate_windows(
        self,
        start_date: datetime,
        end_date: datetime,
        training_days: int,
        testing_days: int,
        step_days: int
    ) -> List[Dict]:
        """
        Generate walk-forward windows.

        Args:
            start_date: Overall start date
            end_date: Overall end date
            training_days: Training window size in days
            testing_days: Testing window size in days
            step_days: How many days to roll forward each iteration

        Returns:
            List of window configurations with training and testing periods
        """
        windows = []
        window_number = 1
        current_start = start_date

        while True:
            # Calculate training period
            training_end = current_start + timedelta(days=training_days)

            # Calculate testing period
            testing_start = training_end
            testing_end = testing_start + timedelta(days=testing_days)

            # Stop if testing period exceeds end date
            if testing_end > end_date:
                break

            windows.append({
                'window_number': window_number,
                'training_start': current_start,
                'training_end': training_end,
                'testing_start': testing_start,
                'testing_end': testing_end,
            })

            # Roll forward
            current_start += timedelta(days=step_days)
            window_number += 1

        self.logger.info(f"Generated {len(windows)} walk-forward windows")
        return windows

    def calculate_performance_degradation(
        self,
        in_sample_roi: Decimal,
        out_sample_roi: Decimal
    ) -> Decimal:
        """
        Calculate performance degradation from in-sample to out-of-sample.

        Returns:
            Percentage drop (positive means performance decreased)
        """
        if in_sample_roi == 0:
            return Decimal('0.00')

        degradation = ((in_sample_roi - out_sample_roi) / abs(in_sample_roi)) * 100
        return Decimal(str(round(float(degradation), 2)))

    def calculate_consistency_score(
        self,
        window_results: List[Dict]
    ) -> Decimal:
        """
        Calculate consistency score across all windows.

        Measures:
        - How consistent out-of-sample results are
        - Lower variance = higher consistency

        Returns:
            Score from 0-100 (100 = perfectly consistent)
        """
        if not window_results:
            return Decimal('0.00')

        # Extract out-of-sample ROIs
        out_sample_rois = [
            float(w.get('out_sample_roi', 0))
            for w in window_results
            if w.get('out_sample_roi') is not None
        ]

        if len(out_sample_rois) < 2:
            return Decimal('50.00')  # Not enough data

        # Calculate coefficient of variation (CV)
        mean_roi = statistics.mean(out_sample_rois)
        std_roi = statistics.stdev(out_sample_rois)

        if mean_roi == 0:
            return Decimal('0.00')

        cv = abs(std_roi / mean_roi)

        # Convert CV to score (lower CV = higher score)
        # CV of 0.5 or less = good (score 80+)
        # CV of 1.0 or more = poor (score 50 or less)
        if cv <= 0.25:
            score = 95
        elif cv <= 0.5:
            score = 80
        elif cv <= 0.75:
            score = 65
        elif cv <= 1.0:
            score = 50
        else:
            score = max(20, 50 - int((cv - 1.0) * 30))

        return Decimal(str(score))

    def assess_robustness(
        self,
        avg_in_sample_roi: Decimal,
        avg_out_sample_roi: Decimal,
        performance_degradation: Decimal,
        consistency_score: Decimal,
        profitable_windows_pct: Decimal
    ) -> Tuple[bool, str]:
        """
        Assess if strategy is robust based on walk-forward results.

        Criteria for robust strategy:
        1. Out-of-sample ROI is positive
        2. Performance degradation is acceptable (<50%)
        3. Consistency score is reasonable (>50)
        4. Majority of windows are profitable (>60%)

        Returns:
            (is_robust: bool, explanation: str)
        """
        reasons = []
        is_robust = True

        # Check 1: Out-of-sample profitability
        if avg_out_sample_roi <= 0:
            is_robust = False
            reasons.append(f"❌ Out-of-sample ROI is negative ({avg_out_sample_roi:.2f}%)")
        else:
            reasons.append(f"✅ Out-of-sample ROI is positive ({avg_out_sample_roi:.2f}%)")

        # Check 2: Performance degradation
        if performance_degradation > 50:
            is_robust = False
            reasons.append(f"❌ High performance degradation ({performance_degradation:.1f}% drop)")
        elif performance_degradation > 30:
            reasons.append(f"⚠️ Moderate performance degradation ({performance_degradation:.1f}% drop)")
        else:
            reasons.append(f"✅ Acceptable performance degradation ({performance_degradation:.1f}% drop)")

        # Check 3: Consistency
        if consistency_score < 40:
            is_robust = False
            reasons.append(f"❌ Low consistency across windows (score: {consistency_score:.0f}/100)")
        elif consistency_score < 60:
            reasons.append(f"⚠️ Moderate consistency (score: {consistency_score:.0f}/100)")
        else:
            reasons.append(f"✅ Good consistency across windows (score: {consistency_score:.0f}/100)")

        # Check 4: Profitable windows percentage
        if profitable_windows_pct < 50:
            is_robust = False
            reasons.append(f"❌ Only {profitable_windows_pct:.0f}% of windows profitable")
        elif profitable_windows_pct < 70:
            reasons.append(f"⚠️ {profitable_windows_pct:.0f}% of windows profitable")
        else:
            reasons.append(f"✅ {profitable_windows_pct:.0f}% of windows profitable")

        # Additional check: If in-sample is unprofitable, strategy is fundamentally flawed
        if avg_in_sample_roi <= 0:
            is_robust = False
            reasons.append(f"❌ Strategy unprofitable even in-sample ({avg_in_sample_roi:.2f}%)")

        explanation = "\n".join(reasons)

        if is_robust:
            verdict = "\n\n✅ VERDICT: Strategy appears ROBUST and suitable for live trading."
        else:
            verdict = "\n\n❌ VERDICT: Strategy shows OVERFITTING or fundamental flaws. Not recommended for live trading."

        return is_robust, explanation + verdict

    def calculate_aggregate_metrics(
        self,
        window_results: List[Dict]
    ) -> Dict:
        """
        Calculate aggregate metrics across all windows.

        Returns:
            Dictionary with aggregated performance metrics
        """
        if not window_results:
            return {}

        # Collect metrics
        in_sample_win_rates = []
        out_sample_win_rates = []
        in_sample_rois = []
        out_sample_rois = []
        profitable_out_sample = 0

        for window in window_results:
            if window.get('in_sample_win_rate') is not None:
                in_sample_win_rates.append(float(window['in_sample_win_rate']))
            if window.get('out_sample_win_rate') is not None:
                out_sample_win_rates.append(float(window['out_sample_win_rate']))
            if window.get('in_sample_roi') is not None:
                in_sample_rois.append(float(window['in_sample_roi']))
            if window.get('out_sample_roi') is not None:
                roi = float(window['out_sample_roi'])
                out_sample_rois.append(roi)
                if roi > 0:
                    profitable_out_sample += 1

        # Calculate averages
        avg_in_sample_wr = Decimal(str(round(statistics.mean(in_sample_win_rates), 2))) if in_sample_win_rates else Decimal('0.00')
        avg_out_sample_wr = Decimal(str(round(statistics.mean(out_sample_win_rates), 2))) if out_sample_win_rates else Decimal('0.00')
        avg_in_sample_roi = Decimal(str(round(statistics.mean(in_sample_rois), 2))) if in_sample_rois else Decimal('0.00')
        avg_out_sample_roi = Decimal(str(round(statistics.mean(out_sample_rois), 2))) if out_sample_rois else Decimal('0.00')

        # Calculate performance degradation
        perf_degradation = self.calculate_performance_degradation(
            avg_in_sample_roi,
            avg_out_sample_roi
        )

        # Calculate consistency score
        consistency = self.calculate_consistency_score(window_results)

        # Calculate profitable windows percentage
        profitable_pct = Decimal(str(round((profitable_out_sample / len(out_sample_rois)) * 100, 1))) if out_sample_rois else Decimal('0.00')

        # Assess robustness
        is_robust, robustness_notes = self.assess_robustness(
            avg_in_sample_roi,
            avg_out_sample_roi,
            perf_degradation,
            consistency,
            profitable_pct
        )

        return {
            'avg_in_sample_win_rate': avg_in_sample_wr,
            'avg_out_sample_win_rate': avg_out_sample_wr,
            'avg_in_sample_roi': avg_in_sample_roi,
            'avg_out_sample_roi': avg_out_sample_roi,
            'performance_degradation': perf_degradation,
            'consistency_score': consistency,
            'profitable_windows_pct': profitable_pct,
            'is_robust': is_robust,
            'robustness_notes': robustness_notes,
        }

    def validate_configuration(
        self,
        start_date: datetime,
        end_date: datetime,
        training_days: int,
        testing_days: int,
        step_days: int
    ) -> Tuple[bool, str]:
        """
        Validate walk-forward configuration.

        Returns:
            (is_valid: bool, error_message: str)
        """
        # Check date range
        total_days = (end_date - start_date).days
        min_required_days = training_days + testing_days

        if total_days < min_required_days:
            return False, f"Date range ({total_days} days) too short. Need at least {min_required_days} days."

        # Check window sizes
        if training_days < 30:
            return False, "Training window should be at least 30 days for meaningful optimization."

        if testing_days < 7:
            return False, "Testing window should be at least 7 days for meaningful validation."

        if step_days < 1:
            return False, "Step size must be at least 1 day."

        # Estimate number of windows
        windows = self.generate_windows(start_date, end_date, training_days, testing_days, step_days)

        if len(windows) < 3:
            return False, f"Configuration yields only {len(windows)} window(s). Need at least 3 for reliable analysis."

        if len(windows) > 50:
            return False, f"Configuration yields {len(windows)} windows. Maximum is 50 to avoid excessive computation."

        return True, f"Configuration valid. Will generate {len(windows)} windows."
