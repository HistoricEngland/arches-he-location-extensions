import uuid
from arches.app.functions.base import BaseFunction
from arches.app.models import models
from arches.app.models.tile import Tile
from arches.app.models.concept import Concept
from django.contrib.gis.geos import GEOSGeometry
from arches.app.models import models
from django.utils.translation import get_language
import logging
import json
from arches_he_location_extensions.geometry_service_backends import (
    GeometryServiceBackend,
)
# from datetime import datetime
import requests

logger = logging.getLogger(__name__)

details = {
    "name": "Generate Related Area From Map",
    "type": "node",
    "description": "Creates a Related Area record for the location of a drawing saved on a Map where Area Name is a string",
    "defaultconfig": {
        "webservice": "",
        "geojson_input_node": "",
        "relatedarea_name_output_node": "",
        "geojson_input_nodegroup": "",
        "relatedarea_name_output_nodegroup": "",
        "relatedareatype_output_node": "",
        "triggering_nodegroups": [],
    },
    "classname": "GenerateRelatedAreaFromMap",
    "component": "views/components/functions/generate_related_area_from_map_function",
    "functionid": "e2af3585-dd90-4f14-a9bf-50b4b9147060",
}


class GenerateRelatedAreaFromMap(BaseFunction):
    notFound = "NotFound"

    def get(self):
        raise NotImplementedError
    
    def getDomainOptionsDict(self, nodeid):
        """
        Returns configured values for a node in {value: valueid} format.
        For concept-backed nodes this reads values from node.config['rdmCollection'].
        """
        options_lookup = {}
        node = models.Node.objects.get(nodeid=nodeid)
        rdm_collection = node.config.get("rdmCollection")

        if rdm_collection:
            # tuple format: (conceptid, valueto, valueid)
            for _, value, valueid in Concept().get_child_collections(rdm_collection):
                if value is not None and valueid is not None:
                    options_lookup[value] = valueid

        return options_lookup
    
    def mapRelatedAreaTypeLabel(self, webservice_label):
        """
        Maps webservice labels to the Arches Related Area Type labels.
        """
        mapping = {
            "Greater London Authority": "County",
            "County": "County",
            "London Borough": "Borough",
            "Metropolitan District": "District",
            "District": "District",
            "Unitary Authority": "Unitary Authority",
            "Civil Parish or Community": "Parish",
            "Non-Civil Parish or Community": "Non Parish Area",
            # Included for completeness if these labels are returned directly.
            "Borough": "Borough",
            "Ecclesiastical": "Ecclesiastical",
            "Locality": "Locality",
            "Parish": "Parish",
        }

        if webservice_label is None:
            return None

        return mapping.get(webservice_label.strip(), webservice_label.strip())


    def save(self, tile, request, context=None):
        """
        Creates Related Area Concept record(s) from the location defined in a tile's GeoJSON node.
        """
        logger.info("save() method called") 
        try:
            search_location = self.get_search_location_from_geometry(tile)

            if search_location is None:
                return
            
            returned_locations = GeometryServiceBackend(
                self.config["webservice"]
            ).get_location_information(self.config["webservice"], search_location)

            # Searches the Administration Area Name concept list for the name
            # returned by the location search

            if not isinstance(returned_locations, dict):
                logger.warning(
                    "generate_related_area_concept_from_map_function expected dict from backend, got %s",
                    type(returned_locations).__name__,
                )
                return

            self.create_related_area_record(tile, returned_locations)

            return

        except Exception as ex:
            logger.error(str(ex))

    def create_related_area_record(self, tile, returned_locations):
        for k, v in returned_locations.items():
            self.create_related_area_record_tile(k, v, tile)


    def get_search_location_from_geometry(self, tile):
        """
        Returns the search location as a string of easting and northing comma separated e.g. 123456,123456
        or returns None if no location is found.
        """
        srid_lat_long = 4326
        srid_bng_absolute = 27700

        geojsonnode = self.config["geojson_input_node"]
        geojson_value = tile.data[geojsonnode]

        if geojson_value is None:
            return None

        geo_js_features = geojson_value["features"]

        geosgeom_union = GEOSGeometry(json.dumps(geo_js_features[0]["geometry"]))
        geo_js_features = geo_js_features[1:]

        for item in geo_js_features:
            geosgeom_union = geosgeom_union.union(GEOSGeometry(json.dumps(item["geometry"])))

        centroid_point = geosgeom_union.envelope.centroid
        centroid_point = GEOSGeometry(centroid_point, srid=srid_lat_long)
        centroid_point.transform(srid_bng_absolute, False)

        easting, northing = map(lambda coord: str(int(coord)).zfill(6), centroid_point.coords)
        search_location = f"{easting},{northing}"

        return search_location

    def delete(self, tile, request):
        raise NotImplementedError

    def on_import(self, tile):
        raise NotImplementedError

    def after_function_save(self, functionxgraph, request):
        raise NotImplementedError

    def create_related_area_record_tile(self, related_area_name, related_area_type, tile):
        """
        Create a Related Area record only if the Area Name and Area Type Name combination doesn't already exist.
        """
        try:
            related_area_node = self.config["relatedarea_name_output_node"]
            related_area_nodegroup = self.config["relatedarea_name_output_nodegroup"]
            related_area_type_node = self.config["relatedareatype_output_node"]
            
            language = models.Language.objects.get(code=get_language())
            related_area_name_formatted = {language.code: {"value": related_area_name, "direction": language.default_direction,}}

            related_area_types = self.getDomainOptionsDict(related_area_type_node)
            mapped_related_area_type = self.mapRelatedAreaTypeLabel(related_area_type)

            location_type_uuid = None

            previously_saved_tiles = Tile.objects.filter(
                nodegroup_id=related_area_nodegroup,
                resourceinstance_id=tile.resourceinstance_id,
            )

            if mapped_related_area_type in related_area_types.keys():
                location_type_uuid = related_area_types[mapped_related_area_type]
            else:
                pass

            if len(previously_saved_tiles) > 0:
                if (
                    self.tile_already_exists(
                        previously_saved_tiles,
                        related_area_name_formatted,
                        location_type_uuid,
                        related_area_node,
                        related_area_type_node,
                    )
                    == False
                ):
                    self.create_new_tile(
                        tile,
                        related_area_nodegroup,
                        related_area_name_formatted,
                        related_area_node,
                        location_type_uuid,
                        related_area_type_node,
                    )
                else:
                    pass
            else:
                self.create_new_tile(
                    tile,
                    related_area_nodegroup,
                    related_area_name_formatted,
                    related_area_node,
                    location_type_uuid,
                    related_area_type_node,
                )

            return

        except (
            KeyboardInterrupt,
            SystemExit,
            ImportError,
            RuntimeError,
            SyntaxError,
        ) as c:
            logger.critical(str(c))

        except (
            AttributeError,
            EOFError,
            LookupError,
            NameError,
            MemoryError,
            ValueError,
            IOError,
        ) as e:
            logger.error(str(e))

        except Warning as w:
            logger.warning(str(w))

        except Exception as ex:
            logger.error(str(ex))

    def create_new_tile(self, tile, nodegroup, nodevalue, nodeuuid, nodetypevalue, nodetypeuuid):
        try:
            new_tile = Tile().get_blank_tile_from_nodegroup_id(
                nodegroup,
                resourceid=tile.resourceinstance_id,
                parenttile=tile.parenttile,
            )
            new_tile.data[nodeuuid] = nodevalue
            new_tile.data[nodetypeuuid] = nodetypevalue
            new_tile.save()

        except Exception as ex:
            self.logger.error(str(ex))

    def tile_already_exists(
        self,
        tiles,
        location_value,
        location_type_value,
        area_name_output_node,
        area_type_output_node,
    ):
        """
        Checks if the resource's tiles already have the Location Name/Location Type Name combination.

        Returns True if the key/value combination already exists or there is an error, and False if the
        key/value combination doesn't already exist.
        """

        try:
            return any(
                t.data[area_name_output_node] == location_value and t.data[area_type_output_node] == location_type_value for t in tiles
            )
        except Exception as ex:
            self.logger.error(str(ex))
            return True
