import abc
from urllib.parse import urlparse


class BaseRelatedAreaConceptBackend(abc.ABC):

    notFound = "NotFound"

    @abc.abstractmethod
    def get_location_information(self, webservice, lat_long_value):
        """
        Abstract method to retrieve the related area concept for a given location ID.
        Must be implemented by subclasses.

        :param webservice: The URL of the webservice to query for location information.
        :param lat_long_value: The latitude and longitude value for which to retrieve location information.
        :return: The location information associated with the given latitude and longitude value.
        """


class GeometryServiceBackend:
    """Factory class that instantiates the appropriate geometry service backend based on webservice URL."""

    def __new__(cls, webservice_url=None):
        """
        Factory method that returns an instance of the appropriate backend.
        If no webservice_url is provided, defaults to the first available backend.
        """
        from arches_he_location_extensions.geometry_service_backends.geometry_service_backend_arcgis import (
            GeometryServiceBackendArcGIS,
        )

        GEOMETRY_SERVICE_BACKENDS = {
            "arcgis": GeometryServiceBackendArcGIS,
        }

        DEFAULT_GEOMETRY_SERVICE_BACKEND = next(iter(GEOMETRY_SERVICE_BACKENDS), "")

        if webservice_url:
            backend_name = infer_geometry_service_backend(webservice_url)
        else:
            backend_name = DEFAULT_GEOMETRY_SERVICE_BACKEND

        if backend_name and backend_name in GEOMETRY_SERVICE_BACKENDS:
            backend_class = GEOMETRY_SERVICE_BACKENDS[backend_name]
            return backend_class()
        else:
            # Fallback to ArcGIS if no backend is inferred
            return GeometryServiceBackendArcGIS()


def infer_geometry_service_backend(webservice_url):
    """Infers the geometry service backend based on the provided webservice URL. It checks for specific keywords in the URL to determine the appropriate backend to use."""
    parsed_url = urlparse(webservice_url)
    hostname = (parsed_url.hostname or "").lower()
    path = (parsed_url.path or "").lower()

    if "arcgis" in hostname or "arcgis" in path:
        return "arcgis"
    else:
        return None
