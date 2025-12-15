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
from signals.views_public_dashboard_optimized import (
    optimized_dashboard,
    dashboard_lightweight,
    clear_dashboard_cache
)
from signals.views_public_paper_trading import (
    public_paper_trades_list,
    public_performance,
    public_open_positions,
    public_summary,
    public_close_trade
)
from signals.views_backtest import BacktestViewSet
from signals.views_strategy_performance import strategy_performance
from signals.views_strategy_performance_optimized import (
    strategy_performance_optimized,
    strategy_performance_lite,
    clear_performance_cache
)
from signals.views_futures import (
    futures_settings,
    toggle_futures_trading,
    futures_trades_list,
    futures_open_positions,
    close_futures_trade,
    futures_summary,
    futures_trade_detail
)
from signals.views_market import get_order_book
from signals.views_chart import chart_annotations, delete_annotation, fibonacci_setup
from signals.views_blacklist import BlacklistedSymbolViewSet

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

# Blacklist endpoints
router.register(r'blacklist', BlacklistedSymbolViewSet, basename='blacklist')

urlpatterns = [
    path('health/', views.health_check, name='health-check'),
    path('trading-session/', views.trading_session_status, name='trading-session'),

    # Public paper trading endpoints (no auth required)
    path('public/paper-trading/', public_paper_trades_list, name='public-paper-trades'),
    path('public/paper-trading/performance/', public_performance, name='public-performance'),
    path('public/paper-trading/open-positions/', public_open_positions, name='public-open-positions'),
    path('public/paper-trading/summary/', public_summary, name='public-summary'),
    path('public/paper-trading/<int:trade_id>/close/', public_close_trade, name='public-close-trade'),
    path('public/paper-trading/dashboard/', public_paper_trading_dashboard, name='public-dashboard'),

    # OPTIMIZED Dashboard endpoints (10x faster)
    path('public/dashboard/v2/', optimized_dashboard, name='optimized-dashboard'),  # Recommended
    path('public/dashboard/lite/', dashboard_lightweight, name='lite-dashboard'),   # Ultra-fast
    path('public/dashboard/clear-cache/', clear_dashboard_cache, name='clear-dashboard-cache'),

    # Strategy Performance endpoints
    path('strategy/performance/', strategy_performance, name='strategy-performance'),  # Original (requires auth)

    # OPTIMIZED Strategy Performance endpoints (10-50x faster, public access)
    path('strategy/performance/v2/', strategy_performance_optimized, name='strategy-performance-v2'),  # Recommended
    path('strategy/performance/lite/', strategy_performance_lite, name='strategy-performance-lite'),   # Ultra-fast
    path('strategy/performance/clear-cache/', clear_performance_cache, name='clear-performance-cache'),


    # Futures Trading endpoints
    path('futures/settings/', futures_settings, name='futures-settings'),
    path('futures/toggle/', toggle_futures_trading, name='futures-toggle'),
    path('futures/trades/', futures_trades_list, name='futures-trades'),
    path('futures/trades/<int:trade_id>/', futures_trade_detail, name='futures-trade-detail'),
    path('futures/trades/<int:trade_id>/close/', close_futures_trade, name='futures-close-trade'),
    path('futures/positions/', futures_open_positions, name='futures-positions'),
    path('futures/summary/', futures_summary, name='futures-summary'),

    # Market Data endpoints
    path('market/orderbook/<str:symbol>/', get_order_book, name='orderbook'),

    # Chart Annotations endpoints
    path('chart/annotations/<str:symbol>/', chart_annotations, name='chart-annotations'),
    path('chart/annotations/', chart_annotations, name='chart-annotations-create'),
    path('chart/annotations/<int:annotation_id>/delete/', delete_annotation, name='delete-annotation'),
    path('chart/fib/<str:symbol>/', fibonacci_setup, name='fibonacci-setup'),

    # Router URLs (includes user-specific paper-trades)
    path('', include(router.urls)),
]


