import logging
import math

from arches.app.search.components.base import BaseSearchFilter
from arches.app.search.components.map_filter import _buffer
from arches.app.search.elasticsearch_dsl_builder import Bool, GeoShape, Nested, Terms
from arches.app.utils.betterJSONSerializer import JSONDeserializer

logger = logging.getLogger(__name__)

details = {
    "searchcomponentid": "2f312f1c-7dbb-4112-a364-fd3e954deb8e",
    "name": "LatLong Filter",
    "icon": "fa fa-map-marker",
    "modulename": "latlong-filter.py",
    "classname": "LatLongFilter",
    "type": "latlong-filter-type",
    "componentpath": "views/components/search/latlong-filter",
    "componentname": "latlong-filter",
    "config": {"layoutType": "popup"},
}


class LatLongFilter(BaseSearchFilter):
    def append_dsl(self, search_query_object, **kwargs):
        latlong_filter = JSONDeserializer().deserialize(
            kwargs.get("querystring", "{}")
        )

        try:
            longitude = float(latlong_filter["longitude"])
            latitude = float(latlong_filter["latitude"])
            buffer_radius = float(latlong_filter.get("buffer") or 0)
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "LatLong Filter: ignoring filter with invalid values %s",
                latlong_filter,
            )
            return

        if (
            not math.isfinite(longitude)
            or not math.isfinite(latitude)
            or not math.isfinite(buffer_radius)
            or not (-180 <= longitude <= 180)
            or not (-90 <= latitude <= 90)
            or buffer_radius < 0
        ):
            logger.warning(
                "LatLong Filter: ignoring invalid coordinates or buffer %s",
                latlong_filter,
            )
            return

        point = {"type": "Point", "coordinates": [longitude, latitude]}
        # the analysis SRID is projected in metres, so the radius needs no conversion
        search_geometry = JSONDeserializer().deserialize(
            _buffer(point, buffer_radius, "m").geojson
        )

        geoshape = GeoShape(
            field="geometries.geom.features.geometry",
            type=search_geometry["type"],
            coordinates=search_geometry["coordinates"],
        )

        spatial_query = Bool()
        if latlong_filter.get("inverted", False):
            spatial_query.must_not(geoshape)
        else:
            spatial_query.filter(geoshape)

        spatial_query.filter(
            Terms(
                field="geometries.nodegroup_id",
                terms=kwargs.get("permitted_nodegroups"),
            )
        )

        include_provisional = kwargs.get("include_provisional")
        if include_provisional is False:
            spatial_query.filter(
                Terms(field="geometries.provisional", terms=["false"])
            )
        elif include_provisional == "only provisional":
            spatial_query.filter(Terms(field="geometries.provisional", terms=["true"]))

        search_query = Bool()
        search_query.filter(Nested(path="geometries", query=spatial_query))
        search_query_object["query"].add_query(search_query)
