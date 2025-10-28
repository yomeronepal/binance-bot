"""
Signal admin configuration
"""
from django.contrib import admin
from .models import Signal


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'signal_type', 'entry_price', 'confidence', 'status', 'created_at')
    list_filter = ('signal_type', 'status', 'created_at')
    search_fields = ('symbol', 'description')
    readonly_fields = ('created_at', 'updated_at')
