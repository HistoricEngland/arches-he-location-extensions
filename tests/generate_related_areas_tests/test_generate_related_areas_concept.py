import os
import json
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.contrib.gis.geos import GEOSGeometry
from django.core import management
from django.test import TestCase
from django.test import override_settings

from arches.app.models import models
from arches.app.models.concept import Concept
from arches.app.models.graph import Graph

import logging

from arches_he_location_extensions.functions.generate_related_area_concept_from_map_function import (
    GenerateRelatedAreaConceptFromMap,
)
from arches_he_location_extensions.geometry_service_backends.geometry_service_backend_arcgis import (
    GeometryServiceBackendArcGIS,
)
from tests.generate_related_areas_tests.base_test import (
    CONCEPT_ARCGIS_LAYER_QUERY_RESPONSES,
    CONCEPT_TEST_GEOMETRY,
    EXPECTED_RETURNED_LOCATIONS_CONCEPT,
    mock_arcgis_requests,
)

logger = logging.getLogger(__name__)

# these tests can be run from the command line via
# python manage.py test tests.generate_related_areas_tests.test_generate_related_areas_concept --settings="tests.test_settings"
# or if using docker
# python manage.py test tests.generate_related_areas_tests.test_generate_related_areas_concept --settings="tests.test_settings_for_docker"


class GenerateRelatedAreasConceptTests(TestCase):

    test_model_graph_id = "c06426fd-40a3-473c-ae64-a1e95a6fca83"
    function_id = "e2af3585-dd90-4f14-a9bf-50b4b9147059"

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.get(username="admin")

        # Import ontology once
        ontology_source = os.path.join(
            "tests", "fixtures", "pkg", "ontologies", "cidoc_crm"
        )
        management.call_command("load_ontology", "-s", ontology_source)

        # Import reference data (concepts and collections) required by concept/domain lookups
        for ref_data_file in [
            os.path.join(
                "tests",
                "fixtures",
                "pkg",
                "reference_data",
                "concepts",
                "Administrative Area Type.xml",
            ),
            os.path.join(
                "tests",
                "fixtures",
                "pkg",
                "reference_data",
                "concepts",
                "Administrative Area.xml",
            ),
            os.path.join(
                "tests",
                "fixtures",
                "pkg",
                "reference_data",
                "collections",
                "collections.xml",
            ),
        ]:
            management.call_command(
                "packages", "-o", "import_reference_data", "-s", ref_data_file
            )

        # Import and publish test graph once
        graph_source = os.path.join(
            "tests",
            "fixtures",
            "pkg",
            "graphs",
            "resource_models",
            "generate_related_area_concept_test_model.json",
        )
        management.call_command("packages", "-o", "import_graphs", "-s", graph_source)

        graph = Graph.objects.get(graphid=cls.test_model_graph_id)
        graph.publish(user=cls.admin)

    @classmethod
    def tearDownClass(cls):
        """
        Remove any test-created data:
        - Delete resource instances created for the test graph
        - Delete the test graph itself
        """
        try:
            models.ResourceInstance.objects.filter(
                graph_id=cls.test_model_graph_id
            ).delete()
        except Exception:
            pass

        try:
            Graph.objects.filter(graphid=cls.test_model_graph_id).delete()
        except Exception:
            pass

        super().tearDownClass()

    def _build_function_instance(self):
        function_x_graph = models.FunctionXGraph.objects.get(
            function_id=self.function_id,
            graph_id=self.test_model_graph_id,
        )
        function_instance = GenerateRelatedAreaConceptFromMap()
        function_instance.config = dict(function_x_graph.config)
        function_instance.config["webservice"] = (
            "https://services.arcgis.com/fake/FeatureServer"
        )
        return function_instance

    def _build_input_tile(self, function_instance):
        graph = Graph.objects.get(graphid=self.test_model_graph_id)
        resource = models.ResourceInstance.objects.create(graph=graph)
        geojson_input_node = function_instance.config["geojson_input_node"]

        return SimpleNamespace(
            resourceinstance_id=resource.resourceinstanceid,
            parenttile=None,
            data={
                geojson_input_node: {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "id": "concept-test-feature",
                            "type": "Feature",
                            "geometry": CONCEPT_TEST_GEOMETRY,
                            "properties": {
                                "nodeId": geojson_input_node,
                            },
                        }
                    ],
                }
            },
        )

    def _get_expected_saved_locations(self, function_instance):
        available_concepts = Concept().get(
            id="48457f95-2b62-410e-9022-38a14db8b9f1",
            include_subconcepts=True,
        )
        concept_lookup = {}
        function_instance.returnAreaConceptDetails(available_concepts, concept_lookup)
        available_labels = {str(label) for label in concept_lookup.values()}

        return {
            name: area_type
            for name, area_type in EXPECTED_RETURNED_LOCATIONS_CONCEPT.items()
            if name in available_labels
        }

    def test_01_function_exists(self):
        """
        Test that the GenerateRelatedAreaConceptFromMap function is registered on the
        test graph and that the function class is callable.
        """
        function_x_graph = models.FunctionXGraph.objects.filter(
            function_id=self.function_id,
            graph_id=self.test_model_graph_id,
        )
        self.assertTrue(function_x_graph.exists())
        self.assertIsInstance(
            GenerateRelatedAreaConceptFromMap(),
            GenerateRelatedAreaConceptFromMap,
        )

    def test_02_save_get_location_information(self):
        """
        Test save() end-to-end using real function/backend logic and mocked ArcGIS
        API responses from base_test.
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)
        expected_saved_locations = self._get_expected_saved_locations(function_instance)

        related_area_tiles_before = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        ).count()

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests(
                layer_query_responses=CONCEPT_ARCGIS_LAYER_QUERY_RESPONSES,
            ) as mocked_get:
                function_instance.save(tile=tile, request=None)

        related_area_tiles_after = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        ).count()

        self.assertEqual(mocked_get.call_count, 4)
        self.assertEqual(
            related_area_tiles_after - related_area_tiles_before,
            len(expected_saved_locations),
        )

    def test_03_get_layer_numbers_by_names(self):
        backend = GeometryServiceBackendArcGIS()

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests() as mocked_get:
                layer_numbers = backend.get_layer_numbers_by_names(
                    webservice="https://services.arcgis.com/fake/FeatureServer",
                    layer_names=["County", "DIS_UNI_MET", "Parish"],
                )

        self.assertEqual(layer_numbers, [1, 2, 4])
        self.assertEqual(mocked_get.call_count, 1)

    def test_03b_get_location_information_uses_concept_fixtures(self):
        backend = GeometryServiceBackendArcGIS()

        # Build the ArcGIS search coordinate from the provided WGS84 geometry.
        centroid_point = GEOSGeometry(json.dumps(CONCEPT_TEST_GEOMETRY), srid=4326)
        centroid_point.transform(27700, False)
        search_location = (
            f"{str(int(centroid_point.coords[0])).zfill(6)},"
            f"{str(int(centroid_point.coords[1])).zfill(6)}"
        )

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests(
                layer_query_responses=CONCEPT_ARCGIS_LAYER_QUERY_RESPONSES,
            ) as mocked_get:
                returned_locations = backend.get_location_information(
                    webservice="https://services.arcgis.com/fake/FeatureServer",
                    lat_long_value=search_location,
                )

        self.assertEqual(returned_locations, EXPECTED_RETURNED_LOCATIONS_CONCEPT)
        self.assertEqual(mocked_get.call_count, 4)

    def test_04_getDomainOptionsDict(self):
        function_x_graph = models.FunctionXGraph.objects.get(
            function_id=self.function_id,
            graph_id=self.test_model_graph_id,
        )
        related_area_type_node = function_x_graph.config["relatedareatype_output_node"]

        # Assert this test is using the node id configured on the graph fixture.
        self.assertEqual(
            related_area_type_node,
            "78e3d752-5ab3-11f1-b973-72993b47c424",
        )

        function_instance = GenerateRelatedAreaConceptFromMap()
        domain_options = function_instance.getDomainOptionsDict(related_area_type_node)

        self.assertIsInstance(domain_options, dict)
        self.assertTrue(len(domain_options) > 0)
        self.assertIn("County", domain_options)

    def test_05_mapRelatedAreaTypeLabel(self):
        """
        Test mapRelatedAreaTypeLabel using mocked webservice labels.
        """
        function_instance = GenerateRelatedAreaConceptFromMap()

        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("County"),
            "County",
        )
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("District"),
            "District",
        )
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("Civil Parish or Community"),
            "Parish",
        )

        self.assertIsNone(function_instance.mapRelatedAreaTypeLabel(None))
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("  County  "),
            "County",
        )
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("UnknownLabel"),
            "UnknownLabel",
        )

    def test_06_returnAreaConceptDetails(self):
        """
        Test recursive concept extraction for prefLabel values using concepts
        loaded into the test database during setUpTestData.
        """
        function_instance = GenerateRelatedAreaConceptFromMap()
        available_concepts = Concept().get(
            id="48457f95-2b62-410e-9022-38a14db8b9f1",
            include_subconcepts=True,
        )

        concept_lookup = {}
        function_instance.returnAreaConceptDetails(available_concepts, concept_lookup)

        self.assertIsInstance(concept_lookup, dict)
        self.assertTrue(len(concept_lookup) > 0)
        self.assertIn("City of London", concept_lookup.values())
        for key, value in concept_lookup.items():
            self.assertTrue(str(key).strip())
            self.assertTrue(str(value).strip())

    def test_07_save_ignores_empty_api_results(self):
        """
        save() should not create related area tiles when ArcGIS returns no features.
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests(
                layer_query_responses=[
                    {"features": []},
                    {"features": []},
                    {"features": []},
                ],
            ) as mocked_get:
                function_instance.save(tile=tile, request=None)

        related_area_tiles = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        )

        self.assertEqual(mocked_get.call_count, 4)
        self.assertEqual(related_area_tiles.count(), 0)

    def test_08_save(self):
        """
        Test save() creates related area tiles with expected concept IDs and
        mapped area type IDs from ArcGIS API responses.
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)
        expected_saved_locations = self._get_expected_saved_locations(function_instance)

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests(
                layer_query_responses=CONCEPT_ARCGIS_LAYER_QUERY_RESPONSES,
            ):
                function_instance.save(tile=tile, request=None)

        related_area_name_node = function_instance.config[
            "relatedarea_name_output_node"
        ]
        related_area_type_node = function_instance.config["relatedareatype_output_node"]
        related_area_nodegroup = function_instance.config[
            "relatedarea_name_output_nodegroup"
        ]

        related_area_tiles = models.TileModel.objects.filter(
            nodegroup_id=related_area_nodegroup,
            resourceinstance_id=tile.resourceinstance_id,
        )
        self.assertEqual(related_area_tiles.count(), len(expected_saved_locations))

        available_concepts = Concept().get(
            id="48457f95-2b62-410e-9022-38a14db8b9f1",
            include_subconcepts=True,
        )
        concept_lookup = {}
        function_instance.returnAreaConceptDetails(available_concepts, concept_lookup)
        concept_id_by_label = {
            str(label): str(concept_id) for concept_id, label in concept_lookup.items()
        }

        domain_options = function_instance.getDomainOptionsDict(related_area_type_node)

        expected_pairs = set()
        for area_name, returned_area_type in expected_saved_locations.items():
            expected_area_id = concept_id_by_label.get(area_name)
            self.assertIsNotNone(
                expected_area_id,
                f"Concept ID for area name '{area_name}' not found — check concept fixtures.",
            )
            mapped_type_label = function_instance.mapRelatedAreaTypeLabel(
                returned_area_type
            )
            expected_type_id = domain_options.get(mapped_type_label)
            self.assertIsNotNone(
                expected_type_id,
                f"Concept ID not found for area type '{mapped_type_label}' — check concept fixtures.",
            )

            expected_pairs.add((expected_area_id, expected_type_id))

        actual_pairs = set()
        for saved_tile in related_area_tiles:
            actual_pairs.add(
                (
                    str(saved_tile.data[related_area_name_node]),
                    str(saved_tile.data[related_area_type_node]),
                )
            )

        self.assertSetEqual(actual_pairs, expected_pairs)

    def test_09_save_twice_does_not_double_related_area_tiles(self):
        """
        Calling save() a second time should not duplicate related area tiles — the
        tile count after the second save must equal the tile count after the first.
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)
        expected_saved_locations = self._get_expected_saved_locations(function_instance)

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests(
                layer_query_responses=CONCEPT_ARCGIS_LAYER_QUERY_RESPONSES,
            ):
                function_instance.save(tile=tile, request=None)

        tiles_after_first_save = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        ).count()

        self.assertEqual(tiles_after_first_save, len(expected_saved_locations))

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests(
                layer_query_responses=CONCEPT_ARCGIS_LAYER_QUERY_RESPONSES,
            ):
                function_instance.save(tile=tile, request=None)

        tiles_after_second_save = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        ).count()

        self.assertEqual(tiles_after_second_save, tiles_after_first_save)

    def test_10_save_creates_no_tiles_when_geometry_is_absent(self):
        """
        save() should not create any related area tiles when the geometry node
        value is None (i.e. no geometry has been provided).
        """
        function_instance = self._build_function_instance()

        graph = Graph.objects.get(graphid=self.test_model_graph_id)
        resource = models.ResourceInstance.objects.create(graph=graph)
        geojson_input_node = function_instance.config["geojson_input_node"]

        tile = SimpleNamespace(
            resourceinstance_id=resource.resourceinstanceid,
            parenttile=None,
            data={geojson_input_node: None},
        )

        function_instance.save(tile=tile, request=None)

        related_area_tiles = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        )

        self.assertEqual(related_area_tiles.count(), 0)

    def test_11_save_normalises_city_and_county_of_the_city_of_london(self):
        """
        save() should normalise the ArcGIS label "City and County of the City of
        London" to "City of London" when looking up the related area concept.
        The saved tile's area-name node must hold the concept ID for "City of London".
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)

        city_of_london_layer_response = {
            "features": [
                {
                    "attributes": {
                        "NAME": "City and County of the City of London",
                        "DESCRIPTIO": "County",
                    }
                }
            ]
        }

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests(
                layer_query_responses=[
                    city_of_london_layer_response,
                    {"features": []},
                    {"features": []},
                ],
            ):
                function_instance.save(tile=tile, request=None)

        related_area_name_node = function_instance.config[
            "relatedarea_name_output_node"
        ]
        related_area_nodegroup = function_instance.config[
            "relatedarea_name_output_nodegroup"
        ]

        related_area_tiles = models.TileModel.objects.filter(
            nodegroup_id=related_area_nodegroup,
            resourceinstance_id=tile.resourceinstance_id,
        )
        self.assertEqual(related_area_tiles.count(), 1)

        available_concepts = Concept().get(
            id="48457f95-2b62-410e-9022-38a14db8b9f1",
            include_subconcepts=True,
        )
        concept_lookup = {}
        function_instance.returnAreaConceptDetails(available_concepts, concept_lookup)
        city_of_london_concept_id = next(
            str(concept_id)
            for concept_id, label in concept_lookup.items()
            if str(label) == "City of London"
        )

        saved_tile = related_area_tiles.first()
        self.assertEqual(
            str(saved_tile.data[related_area_name_node]),
            city_of_london_concept_id,
        )
