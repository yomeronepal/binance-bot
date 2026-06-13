"""Admin configuration with auto-registration of first-party models.

Replaces the default admin AppConfig. After Django finishes autodiscovering
each app's ``admin`` module (so explicit ModelAdmins are honoured), every
first-party model that is still unregistered is registered with a default
admin. New models added to these apps therefore appear in the admin
automatically, with no manual ``admin.site.register`` call required.
"""
from django.contrib.admin.apps import AdminConfig

LOCAL_APP_LABELS = {
    'signals',
    'scanner',
    'users',
    'api',
    'billing',
    'websocket',
}


class AutoRegisterAdminConfig(AdminConfig):
    """Admin config that auto-registers leftover first-party models."""

    def ready(self):
        """Run default admin autodiscovery, then auto-register models."""
        super().ready()
        self._autoregister_local_models()

    def _autoregister_local_models(self):
        """Register every first-party model not already registered."""
        from django.apps import apps
        from django.contrib import admin

        for model in apps.get_models():
            if model._meta.app_label not in LOCAL_APP_LABELS:
                continue
            if admin.site.is_registered(model):
                continue
            admin.site.register(model)
