from django.apps import AppConfig


class SignalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'signals'

    def ready(self):
        """
        Import signal handlers when app is ready.
        This ensures Django signals are registered.
        """
        import signals.signals_handlers  # noqa
