import os
import uuid

from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.core.management import call_command
from django.conf import settings
from arches.app.models import models
from arches.app.models.graph import Graph
from arches.app.models.resource import Resource
from arches.app.models.tile import Tile
from arches.app.utils.betterJSONSerializer import JSONDeserializer
from arches.app.utils.data_management.resource_graphs.importer import (
    import_graph as resource_graph_importer,
)
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch


class MockArcGISResponse:
	def __init__(self, payload, status_code=200):
		self._payload = payload
		self.status_code = status_code

	def json(self):
		return self._payload


ARCGIS_SERVICE_ROOT_RESPONSE = {
	"currentVersion": 12,
	"serviceItemId": "7ffda142c10048708125373121b54645",
	"serviceDescription": "Where Am I location data for webGIS2.",
	"hasVersionedData": False,
	"supportsDisconnectedEditing": False,
	"hasStaticData": True,
	"hasSharedDomains": False,
	"maxRecordCount": 2000,
	"supportedQueryFormats": "JSON",
	"supportsVCSProjection": False,
	"supportedExportFormats": "csv,shapefile,sqlite,geoPackage,filegdb,featureCollection,geojson,kml,excel",
	"supportedConvertFileFormats": "JSON,PBF",
	"supportedConvertContentFormats": "LayerEditCollection",
	"supportedFullTextLocales": [
		"neutral",
		"ar-SA",
		"bg-BG",
		"bn-IN",
		"ca-ES",
		"cs-CZ",
		"da-DK",
		"de-DE",
		"el-GR",
		"en-GB",
		"en-US",
		"es-ES",
		"fr-FR",
		"gu-IN",
		"he-IL",
		"hi-IN",
		"hr-HR",
		"id-ID",
		"is-IS",
		"it-IT",
		"ja-JP",
		"kn-IN",
		"ko-KR",
		"lt-LT",
		"lv-LV",
		"ml-IN",
		"mr-IN",
		"ms-MY",
		"nb-NO",
		"nl-NL",
		"pa-IN",
		"pl-PL",
		"pt-BR",
		"pt-PT",
		"ro-RO",
		"ru-RU",
		"sk-SK",
		"sl-SI",
		"sr-Cyrl-CS",
		"sr-Latn-CS",
		"sv-SE",
		"ta-IN",
		"te-IN",
		"th-TH",
		"tr-TR",
		"uk-UA",
		"ur-PK",
		"vi-VN",
		"zh-CN",
		"zh-HK",
		"zh-MO",
		"zh-SG",
		"zh-TW",
	],
	"supportsSharedTemplates": True,
	"hasSharedTemplates": True,
	"capabilities": "Query",
	"description": "Where Am I location data (HE Region, County, District/Unitary Authority/Metropolitan Borough/London Borough, National Parks, Parish, Ward, Westminster Constituency, Postcodes, Archdeaconry, Diocese) for webGIS2",
	"copyrightText": "",
	"spatialReference": {"wkid": 27700, "latestWkid": 27700},
	"initialExtent": {
		"xmin": -620667.0378943988,
		"ymin": -182129.0903578914,
		"xmax": 1282169.0378943994,
		"ymax": 1407764.1903578904,
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
	},
	"fullExtent": {
		"xmin": 5512.998499999754,
		"ymin": 5333.277699999511,
		"xmax": 655990.5565,
		"ymax": 1220309.8807999997,
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
	},
	"allowGeometryUpdates": True,
	"supportsTrueCurve": True,
	"trueCurveSupportMode": "OGC",
	"supportedCurveTypes": ["esriGeometryCircularArc"],
	"supportedTrueCurvePbfFeatureEncodings": [
		"esriCompressedShapeBuffer",
		"esriDefault",
	],
	"allowTrueCurvesUpdates": True,
	"onlyAllowTrueCurveUpdatesByTrueCurveClients": False,
	"units": "esriMeters",
	"supportsAppend": True,
	"supportedAppendCapabilities": "Features",
	"supportsSharedDomains": True,
	"supportsWebHooks": True,
	"supportsTemporalLayers": True,
	"layerOverridesEnabled": True,
	"syncEnabled": False,
	"supportsApplyEditsWithGlobalIds": False,
	"supportsReturnDeleteResults": True,
	"supportsLayerOverrides": True,
	"supportsTilesAndBasicQueriesMode": True,
	"supportsQueryContingentValues": True,
	"supportedContingentValuesFormats": "JSON, PBF",
	"supportsContingentValuesJson": 2,
	"advancedEditingCapabilities": {
		"supportsSplit": False,
		"supportsReturnServiceEditsInSourceSR": False,
		"supportsAsyncApplyEdits": True,
		"supportsReturnEditResults": True,
		"supportsApplyEditsbyUploadID": True,
		"supportedApplyEditsUploadIDFormats": "JSON,PBF",
	},
	"editorTrackingInfo": {
		"enableEditorTracking": False,
		"enableOwnershipAccessControl": False,
		"allowOthersToQuery": True,
		"allowOthersToUpdate": True,
		"allowOthersToDelete": True,
		"allowAnonymousToQuery": True,
		"allowAnonymousToUpdate": True,
		"allowAnonymousToDelete": True,
	},
	"xssPreventionInfo": {
		"xssPreventionEnabled": True,
		"xssPreventionRule": "InputOnly",
		"xssInputRule": "rejectInvalid",
	},
	"layers": [
		{
			"id": 0,
			"name": "HE_Region",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 1,
			"name": "County",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 2,
			"name": "DIS_UNI_MET",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 3,
			"name": "National Parks",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 4,
			"name": "Parish",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 5,
			"name": "Ward",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 6,
			"name": "Westminster Constituency",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 7,
			"name": "CodePoint_Polygons",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 8,
			"name": "Church of England Archdeaconries",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 9,
			"name": "Church of England Diocese Regions",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 10,
			"name": "Ceremonial_County",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
		{
			"id": 11,
			"name": "osNamesPoint",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPoint",
		},
		{
			"id": 12,
			"name": "osNamesPoly",
			"parentLayerId": -1,
			"defaultVisibility": False,
			"subLayerIds": None,
			"minScale": 0,
			"maxScale": 0,
			"type": "Feature Layer",
			"geometryType": "esriGeometryPolygon",
		},
	],
	"tables": [],
}


ARCGIS_LAYER_QUERY_RESPONSES = [
	{
		"objectIdFieldName": "OBJECTID",
		"uniqueIdField": {"name": "OBJECTID", "isSystemMaintained": True},
		"globalIdFieldName": "",
		"geometryType": "esriGeometryPolygon",
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
		"fields": [
			{
				"name": "NAME",
				"type": "esriFieldTypeString",
				"alias": "NAME",
				"sqlType": "sqlTypeOther",
				"length": 60,
				"domain": None,
				"defaultValue": None,
			},
			{
				"name": "DESCRIPTIO",
				"type": "esriFieldTypeString",
				"alias": "DESCRIPTIO",
				"sqlType": "sqlTypeOther",
				"length": 50,
				"domain": None,
				"defaultValue": None,
			},
		],
		"features": [{"attributes": {"NAME": "Surrey", "DESCRIPTIO": "County"}}],
	},
	{
		"objectIdFieldName": "OBJECTID",
		"uniqueIdField": {"name": "OBJECTID", "isSystemMaintained": True},
		"globalIdFieldName": "",
		"geometryType": "esriGeometryPolygon",
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
		"fields": [
			{
				"name": "NAME",
				"type": "esriFieldTypeString",
				"alias": "NAME",
				"sqlType": "sqlTypeOther",
				"length": 60,
				"domain": None,
				"defaultValue": None,
			},
			{
				"name": "DESCRIPTIO",
				"type": "esriFieldTypeString",
				"alias": "DESCRIPTIO",
				"sqlType": "sqlTypeOther",
				"length": 50,
				"domain": None,
				"defaultValue": None,
			},
		],
		"features": [
			{"attributes": {"NAME": "Waverley", "DESCRIPTIO": "District"}}
		],
	},
	{
		"objectIdFieldName": "OBJECTID",
		"uniqueIdField": {"name": "OBJECTID", "isSystemMaintained": True},
		"globalIdFieldName": "",
		"geometryType": "esriGeometryPolygon",
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
		"fields": [
			{
				"name": "NAME",
				"type": "esriFieldTypeString",
				"alias": "NAME",
				"sqlType": "sqlTypeOther",
				"length": 60,
				"domain": None,
				"defaultValue": None,
			},
			{
				"name": "DESCRIPTIO",
				"type": "esriFieldTypeString",
				"alias": "DESCRIPTIO",
				"sqlType": "sqlTypeOther",
				"length": 50,
				"domain": None,
				"defaultValue": None,
			},
		],
		"features": [
			{
				"attributes": {
					"NAME": "Witley",
					"DESCRIPTIO": "Civil Parish or Community",
				}
			}
		],
	},
]


EXPECTED_RETURNED_LOCATIONS = {
	"Surrey": "County",
	"Waverley": "District",
	"Witley": "Civil Parish or Community",
}


CONCEPT_TEST_GEOMETRY = {
	"coordinates": [-0.12767290122090458, 51.49887571084383],
	"type": "Point",
}


CONCEPT_ARCGIS_LAYER_QUERY_RESPONSES = [
	{
		"objectIdFieldName": "OBJECTID",
		"uniqueIdField": {"name": "OBJECTID", "isSystemMaintained": True},
		"globalIdFieldName": "",
		"geometryType": "esriGeometryPolygon",
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
		"fields": [
			{
				"name": "NAME",
				"type": "esriFieldTypeString",
				"alias": "NAME",
				"sqlType": "sqlTypeOther",
				"length": 60,
				"domain": None,
				"defaultValue": None,
			},
			{
				"name": "DESCRIPTIO",
				"type": "esriFieldTypeString",
				"alias": "DESCRIPTIO",
				"sqlType": "sqlTypeOther",
				"length": 50,
				"domain": None,
				"defaultValue": None,
			},
		],
		"features": [
			{
				"attributes": {
					"NAME": "Greater London Authority",
					"DESCRIPTIO": "Greater London Authority",
				}
			}
		],
	},
	{
		"objectIdFieldName": "OBJECTID",
		"uniqueIdField": {"name": "OBJECTID", "isSystemMaintained": True},
		"globalIdFieldName": "",
		"geometryType": "esriGeometryPolygon",
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
		"fields": [
			{
				"name": "NAME",
				"type": "esriFieldTypeString",
				"alias": "NAME",
				"sqlType": "sqlTypeOther",
				"length": 60,
				"domain": None,
				"defaultValue": None,
			},
			{
				"name": "DESCRIPTIO",
				"type": "esriFieldTypeString",
				"alias": "DESCRIPTIO",
				"sqlType": "sqlTypeOther",
				"length": 50,
				"domain": None,
				"defaultValue": None,
			},
		],
		"features": [
			{
				"attributes": {
					"NAME": "City of Westminster",
					"DESCRIPTIO": "London Borough",
				}
			}
		],
	},
	{
		"objectIdFieldName": "OBJECTID",
		"uniqueIdField": {"name": "OBJECTID", "isSystemMaintained": True},
		"globalIdFieldName": "",
		"geometryType": "esriGeometryPolygon",
		"spatialReference": {"wkid": 27700, "latestWkid": 27700},
		"fields": [
			{
				"name": "NAME",
				"type": "esriFieldTypeString",
				"alias": "NAME",
				"sqlType": "sqlTypeOther",
				"length": 60,
				"domain": None,
				"defaultValue": None,
			},
			{
				"name": "DESCRIPTIO",
				"type": "esriFieldTypeString",
				"alias": "DESCRIPTIO",
				"sqlType": "sqlTypeOther",
				"length": 50,
				"domain": None,
				"defaultValue": None,
			},
		],
		"features": [
			{
				"attributes": {
					"NAME": "Non Civil Parish",
					"DESCRIPTIO": "Non-Civil Parish or Community",
				}
			}
		],
	},
]


EXPECTED_RETURNED_LOCATIONS_CONCEPT = {
	"Greater London Authority": "Greater London Authority",
	"City of Westminster": "London Borough",
	"Non Civil Parish": "Non-Civil Parish or Community",
}


@contextmanager
def mock_arcgis_requests(
	service_root_response=None,
	layer_query_responses=None,
):
	"""
	Patch ArcGIS HTTP calls used by GeometryServiceBackendArcGIS.

	This returns one service root response followed by one response per queried
	layer in the order the backend requests them.
	"""

	service_payload = deepcopy(service_root_response or ARCGIS_SERVICE_ROOT_RESPONSE)
	query_payloads = deepcopy(layer_query_responses or ARCGIS_LAYER_QUERY_RESPONSES)

	def _mock_get(url, params=None, headers=None, **kwargs):
		if url.endswith("?f=json"):
			return MockArcGISResponse(payload=service_payload, status_code=200)

		if url.endswith("/query"):
			payload = query_payloads.pop(0) if query_payloads else {"features": []}
			return MockArcGISResponse(payload=payload, status_code=200)

		return MockArcGISResponse(payload={}, status_code=404)

	with patch(
		"arches_he_location_extensions.geometry_service_backends.geometry_service_backend_arcgis.requests.get",
		side_effect=_mock_get,
	) as mocked_get:
		yield mocked_get
