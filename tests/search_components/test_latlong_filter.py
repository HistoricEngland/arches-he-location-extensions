import json
from html.parser import HTMLParser
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import get_template
from django.test import SimpleTestCase

from arches.app.search.elasticsearch_dsl_builder import Query

filter_module = import_module("mariner_proj.search_components.latlong-filter")


class LatLongFilterTests(SimpleTestCase):
    def run_filter(self, values, geometry=None, **kwargs):
        if geometry is None:
            geometry = {"type": "Point", "coordinates": [-1.5, 52.25]}
        query = Query(se=None)
        with patch.object(
            filter_module,
            "_buffer",
            return_value=SimpleNamespace(geojson=json.dumps(geometry)),
        ) as buffer:
            filter_module.LatLongFilter().append_dsl(
                {"query": query},
                querystring=json.dumps(values),
                permitted_nodegroups=["allowed-nodegroup"],
                **kwargs,
            )
        return query.dsl["query"], buffer

    # A zero-radius search must use the point and respect search permissions.
    def test_point_without_buffer(self):
        dsl, buffer = self.run_filter(
            {"longitude": -1.5, "latitude": 52.25}, include_provisional=False
        )

        buffer.assert_called_once_with(
            {"type": "Point", "coordinates": [-1.5, 52.25]}, 0, "m"
        )
        nested = dsl["bool"]["filter"][0]["nested"]
        self.assertEqual(nested["path"], "geometries")
        filters = nested["query"]["bool"]["filter"]
        self.assertEqual(
            filters[0]["geo_shape"]["geometries.geom.features.geometry"]["shape"],
            {"type": "Point", "coordinates": [-1.5, 52.25]},
        )
        self.assertEqual(filters[1], {"terms": {"geometries.nodegroup_id": ["allowed-nodegroup"]}})
        self.assertEqual(filters[2], {"terms": {"geometries.provisional": ["false"]}})

    # Decimal radii must reach the buffer helper unchanged in metres.
    def test_decimal_buffer_uses_polygon_in_metres(self):
        polygon = {
            "type": "Polygon",
            "coordinates": [[[-1.5, 52.25], [-1.4, 52.25], [-1.5, 52.25]]],
        }
        dsl, buffer = self.run_filter(
            {"longitude": -1.5, "latitude": 52.25, "buffer": 250.5},
            geometry=polygon,
        )

        buffer.assert_called_once_with(
            {"type": "Point", "coordinates": [-1.5, 52.25]}, 250.5, "m"
        )
        shape = dsl["bool"]["filter"][0]["nested"]["query"]["bool"]["filter"][0]
        self.assertEqual(
            shape["geo_shape"]["geometries.geom.features.geometry"]["shape"],
            polygon,
        )

    # Inversion excludes the shape while retaining provisional restrictions.
    def test_inverted_shape_and_provisional_only(self):
        dsl, _ = self.run_filter(
            {"longitude": 180, "latitude": -90, "buffer": 0, "inverted": True},
            include_provisional="only provisional",
        )

        spatial = dsl["bool"]["filter"][0]["nested"]["query"]["bool"]
        self.assertIn("geo_shape", spatial["must_not"][0])
        self.assertEqual(
            spatial["filter"][1],
            {"terms": {"geometries.provisional": ["true"]}},
        )

    # Malformed coordinates or radii must never reach PostGIS or Elasticsearch.
    def test_invalid_values_do_not_append_a_query(self):
        invalid_values = (
            {"longitude": 181, "latitude": 0},
            {"longitude": 0, "latitude": -91},
            {"longitude": "nan", "latitude": 0},
            {"longitude": 0, "latitude": "inf"},
            {"longitude": 0, "latitude": 0, "buffer": -1},
            {"longitude": 0, "latitude": 0, "buffer": "nan"},
            {"longitude": 0, "latitude": 0, "buffer": "inf"},
            {"longitude": 0, "latitude": 0, "buffer": "bad"},
            {"longitude": "bad", "latitude": 0},
            {"latitude": 0},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertLogs(filter_module.logger, level="WARNING"):
                dsl, buffer = self.run_filter(values)
                self.assertEqual(dsl, {"match_all": {}})
                buffer.assert_not_called()


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.inputs = {}
        self.labels = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag == "input":
            self.inputs[attributes["id"]] = attributes
        if tag == "label":
            self.labels.append(attributes["for"])


class LatLongTemplateTests(SimpleTestCase):
    # Every input needs a distinct label, error target, and help description.
    def test_input_descriptions_and_labels_have_unique_targets(self):
        parser = IdParser()
        parser.feed(get_template("views/components/search/latlong-filter.htm").render())

        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for field in ("longitude", "latitude", "buffer"):
            input_id = f"latlong-filter-{field}"
            self.assertIn(input_id, parser.labels)
            self.assertIn(input_id, parser.inputs)
            help_id = "latlong-filter-coordinates-info" if field == "longitude" else f"{input_id}-info"
            self.assertEqual(
                parser.inputs[input_id]["aria-describedby"].split(),
                [f"{input_id}-error", help_id],
            )
            self.assertIn(help_id, parser.ids)