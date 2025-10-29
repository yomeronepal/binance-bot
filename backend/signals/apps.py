from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class SignalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'signals'

    def ready(self):
        """
        Import signal handlers when app is ready.
        This ensures Django signals are registered.
        """
        try:
            import signals.signals_handlers  # noqa
            logger.info("✅ Signal handlers imported successfully in ready()")
        except Exception as e:
            logger.error(f"❌ Failed to import signal handlers: {e}", exc_info=True)
