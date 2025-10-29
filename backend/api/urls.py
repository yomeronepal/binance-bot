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

app_name = 'api'

# DRF Router for ViewSets
router = DefaultRouter()
router.register(r'symbols', SymbolViewSet, basename='symbol')
router.register(r'signals', SignalViewSet, basename='signal')
router.register(r'subscriptions', UserSubscriptionViewSet, basename='subscription')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'paper-trades', PaperTradeViewSet, basename='paper-trade')  # User-specific (auth required)
router.register(r'dev/paper', PaperAccountViewSet, basename='paper-account')

urlpatterns = [
    path('health/', views.health_check, name='health-check'),

    # Public paper trading endpoints (no auth required)
    path('public/paper-trading/', public_paper_trades_list, name='public-paper-trades'),
    path('public/paper-trading/performance/', public_performance, name='public-performance'),
    path('public/paper-trading/open-positions/', public_open_positions, name='public-open-positions'),
    path('public/paper-trading/summary/', public_summary, name='public-summary'),
    path('public/paper-trading/dashboard/', public_paper_trading_dashboard, name='public-dashboard'),

    # Router URLs (includes user-specific paper-trades)
    path('', include(router.urls)),
]
