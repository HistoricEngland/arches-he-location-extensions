from django.db import migrations, models
from django.utils.translation import gettext as _


class Migration(migrations.Migration):

    dependencies = [
        (
            "arches_he_location_extensions",
            "92000_initial_related_areas_functions_registration",
        )
    ]

    def add_map_widget(apps, schema_editor):
        MapWidget = apps.get_model("models", "Widget")

        if not MapWidget.objects.filter(
            pk="a5f2c3d4-1e6b-47c9-8a0d-3b9e2f4a1d7c"
        ).exists():

            MapWidget.objects.update_or_create(
                widgetid="a5f2c3d4-1e6b-47c9-8a0d-3b9e2f4a1d7c",
                name="map-widget-enhanced",
                component="views/components/widgets/map-enhanced",
                datatype="geojson-feature-collection",
                helptext="Enhanced map widget inheriting from the standard map widget",
                defaultconfig={
                    "basemap": "streets",
                    "geometryTypes": [
                        {"text": "Point", "id": "Point"},
                        {"text": "Line", "id": "Line"},
                        {"text": "Polygon", "id": "Polygon"},
                    ],
                    "overlayConfigs": [],
                    "overlayOpacity": 0.0,
                    "zoom": 0,
                    "maxZoom": 20,
                    "minZoom": 0,
                    "centerX": 0,
                    "centerY": 0,
                    "defaultValueType": None,
                    "defaultValue": None,
                },
            )

    def remove_map_widget(apps, schema_editor):
        MapWidget = apps.get_model("models", "Widget")

        for widget in MapWidget.objects.filter(
            pk="a5f2c3d4-1e6b-47c9-8a0d-3b9e2f4a1d7c"
        ):
            widget.delete()

    operations = [migrations.RunPython(add_map_widget, remove_map_widget)]
