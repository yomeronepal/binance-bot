"""
WebSocket URL routing for signals app.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Real-time signal updates
    re_path(r'ws/signals/$', consumers.SignalsConsumer.as_asgi()),

    # Real-time analytics
    re_path(r'ws/signals/analytics/$', consumers.SignalAnalyticsConsumer.as_asgi()),
]
