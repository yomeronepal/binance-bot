"""Custom admin site that groups the DayTrade models in their own section.

The DayTrade* models physically live in the ``signals`` app, so Django would
normally list them under "Signals". ``get_app_list`` is overridden to lift
them into a dedicated "Day-Trade" section on the admin index.
"""
from django.contrib import admin

DAYTRADE_SECTION_LABEL = 'daytrade'
DAYTRADE_SECTION_NAME = 'Day-Trade'
DAYTRADE_PREFIX = 'DayTrade'


class DayTradeAdminSite(admin.AdminSite):
    """Admin site that surfaces DayTrade models in a separate section."""

    def get_app_list(self, request, app_label=None):
        """Return the app list with DayTrade models split into their own section."""
        app_list = super().get_app_list(request, app_label)
        if app_label is not None:
            return app_list
        return self._split_daytrade_section(app_list)

    def _split_daytrade_section(self, app_list):
        """Move DayTrade models out of the signals group into a Day-Trade group."""
        daytrade_models = []
        for app in app_list:
            if app['app_label'] != 'signals':
                continue
            kept = []
            for model in app['models']:
                if model['object_name'].startswith(DAYTRADE_PREFIX):
                    daytrade_models.append(model)
                else:
                    kept.append(model)
            app['models'] = kept

        if daytrade_models:
            app_list.append({
                'name': DAYTRADE_SECTION_NAME,
                'app_label': DAYTRADE_SECTION_LABEL,
                'app_url': daytrade_models[0]['admin_url'],
                'has_module_perms': True,
                'models': daytrade_models,
            })
        return app_list
