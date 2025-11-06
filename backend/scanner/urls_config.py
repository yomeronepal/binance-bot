"""
URL Configuration for Configuration Management API
"""
from django.urls import path
from scanner.views import config_views

app_name = 'config'

urlpatterns = [
    # Configuration Summary
    path('summary', config_views.config_summary, name='config_summary'),

    # Validation
    path('validate', config_views.validate_configs, name='validate_configs'),

    # Market Detection
    path('detect-market', config_views.detect_market, name='detect_market'),

    # Get Specific Config
    path('<str:market_type>', config_views.get_config, name='get_config'),

    # Audit Log
    path('audit-log', config_views.audit_log, name='audit_log'),

    # Health Check
    path('health', config_views.health_check, name='health_check'),
]
