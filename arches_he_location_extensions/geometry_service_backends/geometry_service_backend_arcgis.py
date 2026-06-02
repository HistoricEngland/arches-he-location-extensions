from arches_he_location_extensions.geometry_service_backends.geometry_service_backend_base import (
    BaseRelatedAreaConceptBackend,
)
import requests
import logging
from django.conf import settings as system_settings

logger = logging.getLogger(__name__)


class GeometryServiceBackendArcGIS(BaseRelatedAreaConceptBackend):

    def get_location_information(self, webservice, lat_long_value):
        """This function retrieves the location information for a given latitude and longitude value from the ArcGIS service. It iterates through the specified layer numbers and returns the first matching location information found."""

        """ These layers are used to determine the related area concept for a given location ID. The layer numbers are based on the ArcGIS service being used and relate to County, District and Parish"""
        # Dynamically get layer numbers based on layer names
        desired_layers = [
            "County",
            "DIS_UNI_MET",
            "Parish",
        ]  # These are the layer names we want to query for location information.  Change as rewquired based on the ArcGIS service being used.
        layer_numbers = self.get_layer_numbers_by_names(webservice, desired_layers)

        if not layer_numbers:
            logger.warning("No matching layers found in the ArcGIS service")
            return {}

        returned_locations = {}

        for layer_number in layer_numbers:
            found_location = []
            try:
                request_url = f"{webservice}/{str(layer_number)}/query"
                request_params = {
                    "f": "json",
                    "geometry": lat_long_value,
                    "geometryType": "esriGeometryPoint",
                    "returnGeometry": False,
                    "outFields": "NAME,DESCRIPTIO",
                }

                response = requests.get(
                    url=request_url,
                    params=request_params,
                    headers={"referer": system_settings.ARCGIS_WEB_SERVICE_REFERER},
                )
                if response.status_code == 200:
                    data = response.json()
                    # Retrieves the required location value as a string from the returned request data

                    if len(data["features"]) > 0:
                        try:
                            location_name = ""
                            for attr in data["features"][0]["attributes"]:

                                if attr.upper() == "NAME":
                                    location_name = data["features"][0]["attributes"][
                                        attr
                                    ]
                                elif attr.upper() == "DESCRIPTIO":
                                    location_type = data["features"][0]["attributes"][
                                        attr
                                    ]
                                else:
                                    pass
                            found_location = [location_name, location_type]
                        except Exception as ex:
                            logger.error(str(ex))

                        if found_location:  # Only add to dict if location was found
                            returned_locations[found_location[0]] = found_location[1]

            except requests.RequestException as e:
                logger.error(f"Request error for layer {layer_number}: {str(e)}")
                continue
            except (KeyError, ValueError) as e:
                logger.error(f"Data parsing error for layer {layer_number}: {str(e)}")
                continue
            except Exception as ex:
                logger.error(f"Unexpected error for layer {layer_number}: {str(ex)}")
                continue

        return returned_locations

    def get_layer_numbers_by_names(self, webservice, layer_names):
        """
        Dynamically retrieve layer numbers from the ArcGIS service based on layer names.

        Args:
            webservice: The ArcGIS service URL
            layer_names: List of layer names to find (e.g., ['County', 'DIS_UNI_MET', 'Parish'])

        Returns:
            List of layer numbers corresponding to the given layer names
        """

        referer_url = system_settings.ARCGIS_WEB_SERVICE_REFERER
        try:
            # Query the service root to get all layer information
            request_url = f"{webservice}?f=json"
            response = requests.get(
                url=request_url,
                headers={"referer": referer_url},
            )

            if response.status_code == 200:
                data = response.json()
                # The 'layers' key contains a list of all layers with their id and name
                layers = data.get("layers", [])

                layer_numbers = []
                for layer_name in layer_names:
                    for layer in layers:
                        if layer.get("name") == layer_name:
                            layer_numbers.append(layer.get("id"))
                            break

                return layer_numbers
            else:
                logger.error(
                    f"Failed to fetch service description: {response.status_code}"
                )
                return []
        except Exception as e:
            logger.error(f"Error fetching layer information: {str(e)}")
            return []
