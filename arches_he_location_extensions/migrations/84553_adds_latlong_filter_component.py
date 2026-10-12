from django.db import migrations

LATLONG_FILTER_ID = "2f312f1c-7dbb-4112-a364-fd3e954deb8e"
STANDARD_SEARCH_VIEW_ID = "69695d63-6f03-4536-8da9-841b07116381"


def add_latlong_filter(apps, schema_editor):
    SearchComponent = apps.get_model("models", "SearchComponent")

    SearchComponent.objects.update_or_create(
        searchcomponentid=LATLONG_FILTER_ID,
        defaults={
            "name": "LatLong Filter",
            "icon": "fa fa-map-marker",
            "modulename": "latlong-filter.py",
            "classname": "LatLongFilter",
            "type": "latlong-filter-type",
            "componentpath": "views/components/search/latlong-filter",
            "componentname": "latlong-filter",
            "config": {"layoutType": "popup"},
        },
    )

    search_view = SearchComponent.objects.get(pk=STANDARD_SEARCH_VIEW_ID)
    linked = search_view.config["linkedSearchFilters"]
    if not any(f["searchcomponentid"] == LATLONG_FILTER_ID for f in linked):
        linked.append(
            {
                "componentname": "latlong-filter",
                "searchcomponentid": LATLONG_FILTER_ID,
                "layoutSortorder": 8,
            }
        )
        search_view.save()


def remove_latlong_filter(apps, schema_editor):
    SearchComponent = apps.get_model("models", "SearchComponent")

    search_view = SearchComponent.objects.get(pk=STANDARD_SEARCH_VIEW_ID)
    search_view.config["linkedSearchFilters"] = [
        f
        for f in search_view.config["linkedSearchFilters"]
        if f["searchcomponentid"] != LATLONG_FILTER_ID
    ]
    search_view.save()

    SearchComponent.objects.filter(pk=LATLONG_FILTER_ID).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("models", "10804_core_search_filters"),
        ("arches_he_location_extensions", "92001_initial_related_areas_functions_registration"),
    ]

    operations = [
        migrations.RunPython(add_latlong_filter, remove_latlong_filter),
    ]
