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

app_name = 'api'

# DRF Router for ViewSets
router = DefaultRouter()
router.register(r'symbols', SymbolViewSet, basename='symbol')
router.register(r'signals', SignalViewSet, basename='signal')
router.register(r'subscriptions', UserSubscriptionViewSet, basename='subscription')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    path('health/', views.health_check, name='health-check'),
    path('', include(router.urls)),
]
