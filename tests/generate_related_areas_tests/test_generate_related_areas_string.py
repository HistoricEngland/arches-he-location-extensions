import os
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth.models import User
from django.core import management
from types import SimpleNamespace

from arches.app.models import models
from arches.app.models.graph import Graph
from arches_he_location_extensions.functions.generate_related_area_from_map_function import (
    GenerateRelatedAreaFromMap,
)
from arches_he_location_extensions.geometry_service_backends.geometry_service_backend_arcgis import (
    GeometryServiceBackendArcGIS,
)
import logging
from tests.generate_related_areas_tests.base_test import (
    EXPECTED_RETURNED_LOCATIONS,
    mock_arcgis_requests,
)

logger = logging.getLogger(__name__)

# these tests can be run from the command line via
# python manage.py test tests.generate_related_areas_tests.test_generate_related_areas_string --settings="tests.test_settings"
# or if using docker
# python manage.py test tests.generate_related_areas_tests.test_generate_related_areas_string --settings="tests.test_settings_for_docker"


class GenerateRelatedAreasStringTests(TestCase):

    test_model_graph_id = "29253694-6ef8-11f1-9b06-3ede97509bf5"

    @classmethod
    def setUpTestData(cls):

        cls.admin = User.objects.get(username="admin")

        # Import ontology once
        ontology_source = os.path.join(
            "tests", "fixtures", "pkg", "ontologies", "cidoc_crm"
        )
        management.call_command("load_ontology", "-s", ontology_source)

        # Import reference data (concepts and collections) required by getDomainOptionsDict
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
            "generate_related_area_string_test_model.json",
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
            function_id="e2af3585-dd90-4f14-a9bf-50b4b9147060",
            graph_id=self.test_model_graph_id,
        )
        function_instance = GenerateRelatedAreaFromMap()
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
                            "id": "string-test-feature",
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [
                                    -0.6595919872262357,
                                    51.12687632194465,
                                ],
                            },
                            "properties": {"nodeId": geojson_input_node},
                        }
                    ],
                }
            },
        )

    def test_01_function_exists(self):
        """
        Test that the GenerateRelatedAreaFromMap function is registered on the test graph
        and that the function class is callable.
        """
        function_x_graph = models.FunctionXGraph.objects.filter(
            function_id="e2af3585-dd90-4f14-a9bf-50b4b9147060",
            graph_id=self.test_model_graph_id,
        )
        self.assertTrue(function_x_graph.exists())
        self.assertIsInstance(GenerateRelatedAreaFromMap(), GenerateRelatedAreaFromMap)

    def test_02_get_location_information(self):
        """
        save() should create related area tiles by running real geometry and backend
        logic with ArcGIS API responses mocked from base_test.
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)

        related_area_tiles_before = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        ).count()

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests() as mocked_get:
                function_instance.save(tile=tile, request=None)

        related_area_tiles_after = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        ).count()

        self.assertEqual(mocked_get.call_count, 4)
        self.assertEqual(
            related_area_tiles_after - related_area_tiles_before,
            len(EXPECTED_RETURNED_LOCATIONS),
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

    def test_04_getDomainOptionsDict(self):
        function_x_graph = models.FunctionXGraph.objects.get(
            function_id="e2af3585-dd90-4f14-a9bf-50b4b9147060",
            graph_id=self.test_model_graph_id,
        )
        related_area_type_node = function_x_graph.config["relatedareatype_output_node"]

        # Assert this test is using the node id configured on the graph fixture.
        self.assertEqual(
            related_area_type_node,
            "292549b8-6ef8-11f1-9b06-3ede97509bf5",
        )

        function_instance = GenerateRelatedAreaFromMap()
        domain_options = function_instance.getDomainOptionsDict(related_area_type_node)

        self.assertIsInstance(domain_options, dict)
        self.assertTrue(len(domain_options) > 0)
        self.assertIn("County", domain_options)

    def test_05_mapRelatedAreaTypeLabel(self):
        """
        Test the mapRelatedAreaTypeLabel function using the mocked webservice data.
        This verifies that labels returned by the ArcGIS service are correctly mapped
        to Arches Related Area Type labels.
        """
        function_instance = GenerateRelatedAreaFromMap()

        # Test mapping of webservice labels from the mocked ArcGIS responses
        # EXPECTED_RETURNED_LOCATIONS contains: {"Surrey": "County", "Waverley": "District", "Witley": "Civil Parish or Community"}

        self.assertEqual(function_instance.mapRelatedAreaTypeLabel("County"), "County")
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("District"), "District"
        )
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("Civil Parish or Community"),
            "Parish",
        )

        # Test edge cases
        self.assertIsNone(function_instance.mapRelatedAreaTypeLabel(None))
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("  County  "), "County"
        )
        self.assertEqual(
            function_instance.mapRelatedAreaTypeLabel("UnknownLabel"), "UnknownLabel"
        )

    def test_06_get_search_location_from_geometry(self):
        """
        Test get_search_location_from_geometry with a real tile object containing
        GeoJSON geometry data. Verifies the function correctly transforms coordinates
        from WGS84 (lat/lon) to British National Grid (easting/northing).
        """
        function_instance = GenerateRelatedAreaFromMap()
        function_instance.config = {
            "geojson_input_node": "29254c74-6ef8-11f1-9b06-3ede97509bf5"
        }

        # Create a mock tile object with the provided test data
        tile = SimpleNamespace(
            data={
                "29254c74-6ef8-11f1-9b06-3ede97509bf5": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "id": "bd5b166efd170252a8c0fada80189997",
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-0.6595919872262357, 51.12687632194465],
                            },
                            "properties": {
                                "nodeId": "29254c74-6ef8-11f1-9b06-3ede97509bf5"
                            },
                        }
                    ],
                }
            }
        )

        # Call the function and verify it returns a location string
        location = function_instance.get_search_location_from_geometry(tile)

        # Verify location is a string in format "easting,northing"
        self.assertIsInstance(location, str)
        self.assertRegex(location, r"^\d{6},\d{6}$")

        # The coordinates should have been transformed from WGS84 to British National Grid
        # Original point: [-0.6595919872262357, 51.12687632194465]
        # Expected approximate grid reference: 517000,107000 (approximate values)
        parts = location.split(",")
        self.assertEqual(len(parts), 2)
        easting = int(parts[0])
        northing = int(parts[1])

        # Assert we're in a reasonable range for UK coordinates (27700 is EPSG code for BNG)
        self.assertGreater(easting, 0)
        self.assertGreater(northing, 0)
        self.assertLess(easting, 700000)
        self.assertLess(northing, 1250000)

    def test_07_create_related_area_record(self):
        """
        create_related_area_record should write one tile per returned location.
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)

        function_instance.create_related_area_record(tile, EXPECTED_RETURNED_LOCATIONS)

        related_area_node = function_instance.config["relatedarea_name_output_node"]
        related_area_type_node = function_instance.config["relatedareatype_output_node"]
        related_area_tiles = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        )

        domain_options = function_instance.getDomainOptionsDict(related_area_type_node)
        expected_pairs = set()
        for area_name, area_type in EXPECTED_RETURNED_LOCATIONS.items():
            mapped_type_label = function_instance.mapRelatedAreaTypeLabel(area_type)
            expected_type_id = domain_options.get(mapped_type_label)
            self.assertIsNotNone(
                expected_type_id,
                f"Concept ID not found for area type '{mapped_type_label}' — check concept fixtures.",
            )
            expected_pairs.add(
                (
                    area_name,
                    str(expected_type_id),
                )
            )

        actual_pairs = set()
        for saved_tile in related_area_tiles:
            localized_name = saved_tile.data[related_area_node]
            localized_values = (
                list(localized_name.values())
                if isinstance(localized_name, dict)
                else []
            )
            extracted_name = (
                localized_values[0].get("value") if localized_values else None
            )

            self.assertIsNotNone(
                extracted_name,
                f"Failed to extract name from tile data: {localized_name}",
            )

            actual_pairs.add(
                (
                    extracted_name,
                    str(saved_tile.data[related_area_type_node]),
                )
            )
        self.assertEqual(
            related_area_tiles.count(),
            len(EXPECTED_RETURNED_LOCATIONS),
        )
        self.assertSetEqual(actual_pairs, expected_pairs)

    def test_08_save(self):
        """
        save() should be idempotent for the same tile and backend response.
        """
        function_instance = self._build_function_instance()
        tile = self._build_input_tile(function_instance)

        with override_settings(ARCGIS_WEB_SERVICE_REFERER="https://example.org"):
            with mock_arcgis_requests():
                function_instance.save(tile=tile, request=None)

            first_pass_count = models.TileModel.objects.filter(
                nodegroup_id=function_instance.config[
                    "relatedarea_name_output_nodegroup"
                ],
                resourceinstance_id=tile.resourceinstance_id,
            ).count()

            with mock_arcgis_requests():
                function_instance.save(tile=tile, request=None)

        second_pass_count = models.TileModel.objects.filter(
            nodegroup_id=function_instance.config["relatedarea_name_output_nodegroup"],
            resourceinstance_id=tile.resourceinstance_id,
        ).count()

        self.assertEqual(first_pass_count, len(EXPECTED_RETURNED_LOCATIONS))
        self.assertEqual(second_pass_count, first_pass_count)
