"""
API URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from signals.views import (
    SymbolViewSet,
    SignalViewSet,
    UserSubscriptionViewSet,
    AnalyticsViewSet
)
from signals.views_paper_trading import PaperTradeViewSet, PaperAccountViewSet
from signals.views_public_dashboard import public_paper_trading_dashboard
from signals.views_public_paper_trading import (
    public_paper_trades_list,
    public_performance,
    public_open_positions,
    public_summary
)
from signals.views_backtest import (
    BacktestViewSet,
    OptimizationViewSet,
    RecommendationViewSet
)
from signals.views_walkforward import WalkForwardOptimizationViewSet
from signals.views_montecarlo import MonteCarloSimulationViewSet
from signals.views_mltuning import MLTuningJobViewSet, MLModelViewSet
from signals.views_strategy_performance import strategy_performance
from signals.views_optimization import (
    optimization_history,
    config_history,
    active_configs,
    trade_counter_status,
    trigger_manual_optimization,
    optimization_run_detail,
    config_comparison,
    learning_metrics,
    apply_config
)

app_name = 'api'

# DRF Router for ViewSets
router = DefaultRouter()
router.register(r'symbols', SymbolViewSet, basename='symbol')
router.register(r'signals', SignalViewSet, basename='signal')
router.register(r'subscriptions', UserSubscriptionViewSet, basename='subscription')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'paper-trades', PaperTradeViewSet, basename='paper-trade')  # User-specific (auth required)
router.register(r'dev/paper', PaperAccountViewSet, basename='paper-account')

# Backtesting endpoints
router.register(r'backtest', BacktestViewSet, basename='backtest')
router.register(r'optimization', OptimizationViewSet, basename='optimization')
router.register(r'recommendations', RecommendationViewSet, basename='recommendations')

# Walk-Forward Optimization endpoints
router.register(r'walkforward', WalkForwardOptimizationViewSet, basename='walkforward')

# Monte Carlo Simulation endpoints
router.register(r'montecarlo', MonteCarloSimulationViewSet, basename='montecarlo')

# ML-Based Tuning endpoints
router.register(r'mltuning', MLTuningJobViewSet, basename='mltuning')
router.register(r'mlmodels', MLModelViewSet, basename='mlmodel')

urlpatterns = [
    path('health/', views.health_check, name='health-check'),

    # Public paper trading endpoints (no auth required)
    path('public/paper-trading/', public_paper_trades_list, name='public-paper-trades'),
    path('public/paper-trading/performance/', public_performance, name='public-performance'),
    path('public/paper-trading/open-positions/', public_open_positions, name='public-open-positions'),
    path('public/paper-trading/summary/', public_summary, name='public-summary'),
    path('public/paper-trading/dashboard/', public_paper_trading_dashboard, name='public-dashboard'),

    # Strategy Performance endpoints
    path('strategy/performance/', strategy_performance, name='strategy-performance'),

    # Auto-Optimization & Learning endpoints
    path('learning/history/', optimization_history, name='optimization-history'),
    path('learning/configs/', config_history, name='config-history'),
    path('learning/configs/active/', active_configs, name='active-configs'),
    path('learning/counters/', trade_counter_status, name='trade-counters'),
    path('learning/optimize/', trigger_manual_optimization, name='trigger-optimization'),
    path('learning/runs/<str:run_id>/', optimization_run_detail, name='optimization-detail'),
    path('learning/compare/', config_comparison, name='config-comparison'),
    path('learning/metrics/', learning_metrics, name='learning-metrics'),
    path('learning/configs/<int:config_id>/apply/', apply_config, name='apply-config'),

    # Router URLs (includes user-specific paper-trades)
    path('', include(router.urls)),
]
