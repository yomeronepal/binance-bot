"""
Self-Learning Module
Analyzes backtest and optimization results to generate strategy improvement recommendations.
"""
import logging
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

from django.db.models import Avg, Count, Q
from signals.models_backtest import (
    StrategyOptimization,
    OptimizationRecommendation,
    BacktestRun
)

logger = logging.getLogger(__name__)


class SelfLearningModule:
    """
    AI-powered module that learns from backtesting results and generates
    recommendations for strategy improvement.

    Features:
    - Identifies best-performing parameters
    - Discovers symbol/timeframe preferences
    - Generates actionable recommendations
    - Tracks recommendation success rate
    """

    def __init__(self):
        self.confidence_threshold = Decimal('70.0')  # Minimum confidence for recommendations

    def analyze_and_recommend(
        self,
        user=None,
        lookback_days: int = 90,
        min_samples: int = 10
    ) -> List[Dict]:
        """
        Analyze recent optimization results and generate recommendations.

        Args:
            user: User to generate recommendations for (None = all)
            lookback_days: Days of history to analyze
            min_samples: Minimum optimizations needed to make recommendations

        Returns:
            List of recommendation dictionaries
        """
        logger.info(f"🤖 Starting self-learning analysis (lookback: {lookback_days} days)")

        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        # Get recent optimizations
        optimizations = StrategyOptimization.objects.filter(
            tested_at__gte=cutoff_date
        )

        if user:
            optimizations = optimizations.filter(user=user)

        if optimizations.count() < min_samples:
            logger.warning(f"Insufficient data: {optimizations.count()} optimizations (need {min_samples})")
            return []

        logger.info(f"Analyzing {optimizations.count()} optimization results...")

        recommendations = []

        # 1. Analyze parameter performance
        param_recommendations = self._analyze_parameters(optimizations)
        recommendations.extend(param_recommendations)

        # 2. Analyze symbol performance
        symbol_recommendations = self._analyze_symbols(optimizations)
        recommendations.extend(symbol_recommendations)

        # 3. Analyze timeframe performance
        timeframe_recommendations = self._analyze_timeframes(optimizations)
        recommendations.extend(timeframe_recommendations)

        # 4. Analyze risk management
        risk_recommendations = self._analyze_risk_management(optimizations)
        recommendations.extend(risk_recommendations)

        logger.info(f"✅ Generated {len(recommendations)} recommendations")

        return recommendations

    def _analyze_parameters(self, optimizations) -> List[Dict]:
        """
        Analyze which parameter values perform best.

        Returns:
            List of parameter adjustment recommendations
        """
        recommendations = []

        # Group by parameter values
        param_performance = defaultdict(lambda: {'scores': [], 'win_rates': [], 'rois': []})

        for opt in optimizations:
            params = opt.params
            score = float(opt.optimization_score)
            win_rate = float(opt.win_rate)
            roi = float(opt.roi)

            for param_name, param_value in params.items():
                key = f"{param_name}:{param_value}"
                param_performance[key]['scores'].append(score)
                param_performance[key]['win_rates'].append(win_rate)
                param_performance[key]['rois'].append(roi)

        # Find best performing parameter values
        param_averages = {}
        for key, data in param_performance.items():
            if len(data['scores']) < 3:  # Need at least 3 samples
                continue

            param_name, param_value = key.split(':', 1)
            avg_score = np.mean(data['scores'])
            avg_win_rate = np.mean(data['win_rates'])
            avg_roi = np.mean(data['rois'])

            if param_name not in param_averages:
                param_averages[param_name] = []

            param_averages[param_name].append({
                'value': param_value,
                'avg_score': avg_score,
                'avg_win_rate': avg_win_rate,
                'avg_roi': avg_roi,
                'sample_count': len(data['scores'])
            })

        # Generate recommendations for top parameters
        for param_name, values in param_averages.items():
            if len(values) < 2:
                continue

            # Sort by avg_score
            values.sort(key=lambda x: x['avg_score'], reverse=True)
            best = values[0]
            worst = values[-1]

            # Calculate improvement potential
            score_improvement = best['avg_score'] - worst['avg_score']
            win_rate_improvement = best['avg_win_rate'] - worst['avg_win_rate']
            roi_improvement = best['avg_roi'] - worst['avg_roi']

            if score_improvement > 5:  # Significant improvement
                # Calculate confidence based on sample size and consistency
                confidence = self._calculate_confidence(
                    best['sample_count'],
                    score_improvement
                )

                if confidence >= self.confidence_threshold:
                    recommendations.append({
                        'type': 'PARAMETER_ADJUSTMENT',
                        'title': f'Optimize {param_name} parameter',
                        'description': (
                            f'Based on {best["sample_count"]} tests, '
                            f'setting {param_name}={best["value"]} shows '
                            f'{score_improvement:.1f}% better performance.'
                        ),
                        'current_params': {param_name: worst['value']},
                        'recommended_params': {param_name: best['value']},
                        'expected_win_rate_improvement': Decimal(str(win_rate_improvement)),
                        'expected_roi_improvement': Decimal(str(roi_improvement)),
                        'confidence_score': confidence,
                        'evidence_count': best['sample_count']
                    })

        return recommendations

    def _analyze_symbols(self, optimizations) -> List[Dict]:
        """
        Analyze which symbols perform best.

        Returns:
            List of symbol selection recommendations
        """
        recommendations = []

        # Group by symbols
        symbol_performance = defaultdict(lambda: {
            'scores': [],
            'win_rates': [],
            'rois': [],
            'trade_counts': []
        })

        for opt in optimizations:
            if not opt.symbols:
                continue

            score = float(opt.optimization_score)
            win_rate = float(opt.win_rate)
            roi = float(opt.roi)
            trades = opt.total_trades

            for symbol in opt.symbols:
                symbol_performance[symbol]['scores'].append(score)
                symbol_performance[symbol]['win_rates'].append(win_rate)
                symbol_performance[symbol]['rois'].append(roi)
                symbol_performance[symbol]['trade_counts'].append(trades)

        # Calculate averages and rank
        symbol_rankings = []
        for symbol, data in symbol_performance.items():
            if len(data['scores']) < 3:
                continue

            symbol_rankings.append({
                'symbol': symbol,
                'avg_score': np.mean(data['scores']),
                'avg_win_rate': np.mean(data['win_rates']),
                'avg_roi': np.mean(data['rois']),
                'avg_trades': np.mean(data['trade_counts']),
                'sample_count': len(data['scores'])
            })

        if len(symbol_rankings) < 3:
            return recommendations

        # Sort by performance
        symbol_rankings.sort(key=lambda x: x['avg_score'], reverse=True)

        # Identify top performers
        top_symbols = symbol_rankings[:5]
        bottom_symbols = symbol_rankings[-3:]

        # Check if there's significant difference
        if top_symbols[0]['avg_score'] - bottom_symbols[-1]['avg_score'] > 10:
            top_symbol_names = [s['symbol'] for s in top_symbols]
            bottom_symbol_names = [s['symbol'] for s in bottom_symbols]

            avg_top_win_rate = np.mean([s['avg_win_rate'] for s in top_symbols])
            avg_bottom_win_rate = np.mean([s['avg_win_rate'] for s in bottom_symbols])

            confidence = self._calculate_confidence(
                min([s['sample_count'] for s in top_symbols]),
                top_symbols[0]['avg_score'] - bottom_symbols[-1]['avg_score']
            )

            if confidence >= self.confidence_threshold:
                recommendations.append({
                    'type': 'SYMBOL_SELECTION',
                    'title': 'Focus on high-performing symbols',
                    'description': (
                        f'Symbols {", ".join(top_symbol_names[:3])} consistently '
                        f'outperform by {avg_top_win_rate - avg_bottom_win_rate:.1f}% win rate. '
                        f'Consider reducing exposure to {", ".join(bottom_symbol_names)}.'
                    ),
                    'current_params': {'preferred_symbols': bottom_symbol_names},
                    'recommended_params': {'preferred_symbols': top_symbol_names},
                    'expected_win_rate_improvement': Decimal(str(avg_top_win_rate - avg_bottom_win_rate)),
                    'expected_roi_improvement': Decimal(str(
                        top_symbols[0]['avg_roi'] - bottom_symbols[-1]['avg_roi']
                    )),
                    'confidence_score': confidence,
                    'evidence_count': sum(s['sample_count'] for s in top_symbols)
                })

        return recommendations

    def _analyze_timeframes(self, optimizations) -> List[Dict]:
        """
        Analyze which timeframes perform best.

        Returns:
            List of timeframe recommendations
        """
        recommendations = []

        # Group by timeframe
        timeframe_performance = defaultdict(lambda: {
            'scores': [],
            'win_rates': [],
            'rois': []
        })

        for opt in optimizations:
            if not opt.timeframe:
                continue

            timeframe_performance[opt.timeframe]['scores'].append(float(opt.optimization_score))
            timeframe_performance[opt.timeframe]['win_rates'].append(float(opt.win_rate))
            timeframe_performance[opt.timeframe]['rois'].append(float(opt.roi))

        # Find best timeframe
        timeframe_rankings = []
        for tf, data in timeframe_performance.items():
            if len(data['scores']) < 3:
                continue

            timeframe_rankings.append({
                'timeframe': tf,
                'avg_score': np.mean(data['scores']),
                'avg_win_rate': np.mean(data['win_rates']),
                'avg_roi': np.mean(data['rois']),
                'sample_count': len(data['scores'])
            })

        if len(timeframe_rankings) < 2:
            return recommendations

        timeframe_rankings.sort(key=lambda x: x['avg_score'], reverse=True)
        best = timeframe_rankings[0]
        worst = timeframe_rankings[-1]

        if best['avg_score'] - worst['avg_score'] > 10:
            confidence = self._calculate_confidence(
                best['sample_count'],
                best['avg_score'] - worst['avg_score']
            )

            if confidence >= self.confidence_threshold:
                recommendations.append({
                    'type': 'TIMEFRAME_CHANGE',
                    'title': f'Switch to {best["timeframe"]} timeframe',
                    'description': (
                        f'{best["timeframe"]} timeframe shows {best["avg_score"] - worst["avg_score"]:.1f}% '
                        f'better optimization score with {best["avg_win_rate"]:.1f}% win rate.'
                    ),
                    'current_params': {'timeframe': worst['timeframe']},
                    'recommended_params': {'timeframe': best['timeframe']},
                    'expected_win_rate_improvement': Decimal(str(best['avg_win_rate'] - worst['avg_win_rate'])),
                    'expected_roi_improvement': Decimal(str(best['avg_roi'] - worst['avg_roi'])),
                    'confidence_score': confidence,
                    'evidence_count': best['sample_count']
                })

        return recommendations

    def _analyze_risk_management(self, optimizations) -> List[Dict]:
        """
        Analyze risk management parameters (SL/TP ratios, position sizing).

        Returns:
            List of risk management recommendations
        """
        recommendations = []

        # Analyze SL/TP ATR multipliers
        sl_tp_performance = defaultdict(lambda: {
            'scores': [],
            'win_rates': [],
            'max_drawdowns': []
        })

        for opt in optimizations:
            params = opt.params
            if 'sl_atr_multiplier' not in params or 'tp_atr_multiplier' not in params:
                continue

            sl_mult = params['sl_atr_multiplier']
            tp_mult = params['tp_atr_multiplier']
            key = f"{sl_mult}:{tp_mult}"

            sl_tp_performance[key]['scores'].append(float(opt.optimization_score))
            sl_tp_performance[key]['win_rates'].append(float(opt.win_rate))
            sl_tp_performance[key]['max_drawdowns'].append(float(opt.max_drawdown))

        # Find optimal SL/TP ratio
        best_ratio = None
        best_score = 0

        for key, data in sl_tp_performance.items():
            if len(data['scores']) < 3:
                continue

            avg_score = np.mean(data['scores'])
            if avg_score > best_score:
                best_score = avg_score
                sl_mult, tp_mult = key.split(':')
                best_ratio = {
                    'sl_atr_multiplier': float(sl_mult),
                    'tp_atr_multiplier': float(tp_mult),
                    'avg_score': avg_score,
                    'avg_win_rate': np.mean(data['win_rates']),
                    'avg_max_drawdown': np.mean(data['max_drawdowns']),
                    'sample_count': len(data['scores'])
                }

        if best_ratio and best_ratio['sample_count'] >= 5:
            confidence = self._calculate_confidence(
                best_ratio['sample_count'],
                best_ratio['avg_score']
            )

            if confidence >= self.confidence_threshold:
                recommendations.append({
                    'type': 'RISK_ADJUSTMENT',
                    'title': 'Optimize Stop Loss / Take Profit ratios',
                    'description': (
                        f'SL multiplier of {best_ratio["sl_atr_multiplier"]} and '
                        f'TP multiplier of {best_ratio["tp_atr_multiplier"]} '
                        f'achieves {best_ratio["avg_win_rate"]:.1f}% win rate with '
                        f'{best_ratio["avg_max_drawdown"]:.2f}% max drawdown.'
                    ),
                    'current_params': {},
                    'recommended_params': {
                        'sl_atr_multiplier': best_ratio['sl_atr_multiplier'],
                        'tp_atr_multiplier': best_ratio['tp_atr_multiplier']
                    },
                    'expected_win_rate_improvement': Decimal(str(best_ratio['avg_win_rate'])),
                    'expected_roi_improvement': Decimal('0'),
                    'confidence_score': confidence,
                    'evidence_count': best_ratio['sample_count']
                })

        return recommendations

    def _calculate_confidence(self, sample_count: int, improvement: float) -> Decimal:
        """
        Calculate confidence score for recommendation.

        Factors:
        - Sample size (more samples = higher confidence)
        - Improvement magnitude (larger improvement = higher confidence)

        Args:
            sample_count: Number of test samples
            improvement: Performance improvement amount

        Returns:
            Confidence score (0-100)
        """
        # Sample size confidence (0-50 points)
        sample_confidence = min(sample_count / 20 * 50, 50)

        # Improvement confidence (0-50 points)
        improvement_confidence = min(improvement / 20 * 50, 50)

        total_confidence = sample_confidence + improvement_confidence

        return Decimal(str(round(total_confidence, 2)))

    def save_recommendations(
        self,
        recommendations: List[Dict],
        user=None
    ) -> List[OptimizationRecommendation]:
        """
        Save recommendations to database.

        Args:
            recommendations: List of recommendation dictionaries
            user: User to associate recommendations with

        Returns:
            List of created OptimizationRecommendation objects
        """
        saved_recommendations = []

        for rec in recommendations:
            try:
                recommendation = OptimizationRecommendation.objects.create(
                    type=rec['type'],
                    title=rec['title'],
                    description=rec['description'],
                    current_params=rec['current_params'],
                    recommended_params=rec['recommended_params'],
                    expected_win_rate_improvement=rec['expected_win_rate_improvement'],
                    expected_roi_improvement=rec['expected_roi_improvement'],
                    confidence_score=rec['confidence_score'],
                    user=user,
                    status='PENDING'
                )

                saved_recommendations.append(recommendation)
                logger.info(f"💡 Saved recommendation: {recommendation.title}")

            except Exception as e:
                logger.error(f"Error saving recommendation: {e}", exc_info=True)

        return saved_recommendations


# Singleton instance
self_learning_module = SelfLearningModule()
