import uuid
from arches.app.functions.base import BaseFunction
from arches.app.models import models
from arches.app.models.tile import Tile
from arches.app.models.resource import Resource
from arches.app.models.concept import Concept
from django.contrib.gis.geos import GEOSGeometry
import logging
import json
from datetime import datetime
import requests
from arches_he_location_extensions.geometry_service_backends import (
    GeometryServiceBackend,
)

logger = logging.getLogger(__name__)

details = {
    "name": "Generate Related Area Concept From Map",
    "type": "node",
    "description": "Creates a Related Area record for the location of a drawing saved on a Map where Area Name is a concept",
    "defaultconfig": {
        "webservice": "",
        "geojson_input_node": "",
        "relatedarea_name_output_node": "",
        "geojson_input_nodegroup": "",
        "relatedarea_name_output_nodegroup": "",
        "relatedareatype_output_node": "",
        "triggering_nodegroups": [],
    },
    "classname": "GenerateRelatedAreaConceptFromMap",
    "component": "views/components/functions/generate_related_area_concept_from_map_function",
    "functionid": "e2af3585-dd90-4f14-a9bf-50b4b9147059",
}


class GenerateRelatedAreaConceptFromMap(BaseFunction):

    notFound = "NotFound"

    def get(self):
        raise NotImplementedError

    def returnAreaConceptDetails(self, concepts, obj_dict):

        for concept in concepts.values:
            if concept.type == "prefLabel":
                id = concept.id
                val = concept.value
                obj_dict[id] = val
                if concepts.hassubconcepts == True:
                    for subconcept in concepts.subconcepts:
                        self.returnAreaConceptDetails(subconcept, obj_dict)
                else:
                    pass

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

        try:

            # Creates a dictionary of possible Administration Area Name concepts
            # In Keystone this is only three layers deep.

            available_concepts = Concept().get(
                id="48457f95-2b62-410e-9022-38a14db8b9f1", include_subconcepts=True
            )
            concepts_objects = {}
            self.returnAreaConceptDetails(available_concepts, concepts_objects)

            srid_lat_long = 4326
            srid_bng_absolute = 27700

            geojsonnode = self.config["geojson_input_node"]
            geojson_value = tile.data[geojsonnode]

            search_location = None

            if geojson_value != None:

                geo_js_features = geojson_value["features"]

                geosgeom_union = GEOSGeometry(
                    json.dumps(geo_js_features[0]["geometry"])
                )
                geo_js_features = geo_js_features[1:]

                for item in geo_js_features:
                    geosgeom_union = geosgeom_union.union(
                        GEOSGeometry(json.dumps(item["geometry"]))
                    )

                centroid_point = geosgeom_union.envelope.centroid

                centroid_point = GEOSGeometry(centroid_point, srid=srid_lat_long)

                centroid_point.transform(srid_bng_absolute, False)

                easting = str(int(centroid_point.coords[0])).zfill(6)
                northing = str(int(centroid_point.coords[1])).zfill(6)

                search_location = f"{str(easting)},{str(northing)}"

            if search_location is None:
                return  # probably a geojson obj with no geometries

            # This section returns all location results from the Country, District
            # and Parish layers within the rest service

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

            # Normalize concept labels once for resilient matching.
            concept_lookup = {
                str(concept_label).strip().lower(): concept_id
                for concept_id, concept_label in concepts_objects.items()
                if concept_label is not None
            }

            for location_name, location_type in returned_locations.items():
                normalized_location_name = str(location_name).strip()

                if normalized_location_name == "City and County of the City of London":
                    normalized_location_name = "City of London"

                related_area_name = concept_lookup.get(normalized_location_name.lower())

                if related_area_name is not None:
                    self.createRelatedAreaRecord(
                        related_area_name,
                        location_type,
                        tile,
                    )
                else:
                    logger.info(
                        "No related area concept found for returned location '%s'",
                        normalized_location_name,
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

    def delete(self, tile, request):
        raise NotImplementedError

    def on_import(self, tile):
        raise NotImplementedError

    def after_function_save(self, functionxgraph, request):
        raise NotImplementedError

    def createRelatedAreaRecord(self, related_area_name, related_area_type, tile):
        try:
            related_area_node = self.config["relatedarea_name_output_node"]
            related_area_nodegroup = self.config["relatedarea_name_output_nodegroup"]
            related_area_type_node = self.config["relatedareatype_output_node"]

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
                    self.checkIfAlreadyExists(
                        previously_saved_tiles,
                        related_area_name,
                        location_type_uuid,
                        related_area_node,
                        related_area_type_node,
                    )
                    == False
                ):
                    self.createNewTile(
                        tile,
                        related_area_nodegroup,
                        related_area_name,
                        related_area_node,
                        location_type_uuid,
                        related_area_type_node,
                    )
                else:
                    pass
            else:
                self.createNewTile(
                    tile,
                    related_area_nodegroup,
                    related_area_name,
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

    def createNewTile(
        self, tile, nodegroup, nodevalue, nodeuuid, nodetypevalue, nodetypeuuid
    ):
        """Creates a new tile with input information and saves the tile."""

        try:
            new_tile = Tile().get_blank_tile_from_nodegroup_id(
                nodegroup,
                resourceid=tile.resourceinstance_id,
                parenttile=tile.parenttile,
            )
            new_tile.data[nodeuuid] = nodevalue
            new_tile.data[nodetypeuuid] = nodetypevalue
            new_tile.save()

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

    def checkIfAlreadyExists(
        self,
        tiles,
        location_value,
        location_type_value,
        area_name_output_node,
        area_type_output_node,
    ):
        """
        Checks if the resource's tiles already have the Location Value / Location Type Value combination.  Returns True if the
        key/value combination already exists or there is an error and False if the key/value combination doesn't
        already exist.
        """
        found = False
        try:
            for t in tiles:
                if (
                    t.data[area_name_output_node] == location_value
                    and t.data[area_type_output_node] == location_type_value
                ):
                    found = True
                else:
                    pass
            return found

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
