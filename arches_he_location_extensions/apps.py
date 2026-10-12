from django.apps import AppConfig
from django.conf import settings

from arches.settings_utils import generate_frontend_configuration

import logging
logger = logging.getLogger(__name__)


class ArchesHeLocationExtensionsConfig(AppConfig):
    name = "arches_he_location_extensions"
    is_arches_application = True

    def ready(self):
        if settings.APP_NAME.lower() == self.name:
            generate_frontend_configuration()

        if not getattr(settings, "ARCGIS_WEB_SERVICE_REFERER", None):
            logger.warning(
                "ARCGIS_WEB_SERVICE_REFERER is not configured; ArcGIS requests may be rejected."
            )
