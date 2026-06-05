"""
WebSocket URL routing
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/monitoring/$', consumers.NoOpConsumer.as_asgi()),
    re_path(r'ws/backtest/(?P<backtest_id>\d+)/$', consumers.BacktestConsumer.as_asgi()),
]
