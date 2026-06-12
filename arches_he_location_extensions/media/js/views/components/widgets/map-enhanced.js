define([
    'underscore',
    'knockout',
    'knockout-mapping',
    'arches',
    'geojson-extent',
    'views/components/widgets/map',
    'templates/views/components/widgets/map-enhanced.htm',
    'templates/views/components/map-widget-editor.htm',
    'bindings/chosen',
    'bindings/codemirror',
    'select-woo',
    'bindings/fadeVisible',
    'bindings/mapbox-gl',
    'bindings/color-picker',
    'bindings/key-events-click',
], function(_, ko, koMapping, arches, geojsonExtent, MapWidgetViewModel, mapEnhancedTemplate) {

    var EnhancedMapViewModel = function(params) {
        var self = this;

        // Inherit all behaviour from the standard map widget
        MapWidgetViewModel.apply(this, [params]);

        this.reportMap = null;
        this.reportMapPadding = 60;
        this.reportMapMaxZoom = 18;

        this.getReportFeatures = function() {
            var value = koMapping.toJS(self.value);
            var features = (value && value.features) ? value.features : [];

            return _.filter(features, function(feature) {
                return feature && feature.geometry && feature.geometry.type;
            });
        };

        this.reportFeatureCollection = ko.computed(function() {
            return {
                type: 'FeatureCollection',
                features: self.getReportFeatures()
            };
        });

        this.hasReportGeometry = ko.computed(function() {
            return self.reportFeatureCollection().features.length > 0;
        });

        this.reportPinFeatureCollection = ko.computed(function() {
            if (!self.hasReportGeometry()) {
                return {
                    type: 'FeatureCollection',
                    features: []
                };
            }

            var bounds = geojsonExtent(self.reportFeatureCollection());
            // geojsonExtent returns [west, south, east, north]
            var centerX = (bounds[0] + bounds[2]) / 2;
            var centerY = (bounds[1] + bounds[3]) / 2;

            return {
                type: 'FeatureCollection',
                features: [{
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [centerX, centerY]
                    },
                    properties: {
                        source: 'map-widget-enhanced-pin'
                    }
                }]
            };
        });

        this.reportMapStyle = ko.computed(function() {
            var activeBasemap = ko.unwrap(self.activeBasemap);
            var basemapLayers = [];

            if (activeBasemap && Array.isArray(activeBasemap.layer_definitions) && activeBasemap.layer_definitions.length > 0) {
                // Deep clone to avoid mutating shared layer definition objects.
                basemapLayers = JSON.parse(JSON.stringify(activeBasemap.layer_definitions));
            } else {
                basemapLayers = [{
                    id: 'background',
                    type: 'background',
                    paint: {
                        'background-color': '#e5e3df'
                    }
                }];
            }

            var sources = _.extend({}, arches.mapSources || {}, {
                'map-widget-enhanced-report-data': {
                    type: 'geojson',
                    data: self.reportFeatureCollection()
                },
                'map-widget-enhanced-report-pin': {
                    type: 'geojson',
                    data: self.reportPinFeatureCollection()
                }
            });

            var style = {
                version: 8,
                name: 'Map Widget Enhanced Report',
                sources: sources,
                sprite: arches.mapboxSprites,
                glyphs: arches.mapboxGlyphs,
                layers: basemapLayers.concat([
                    {
                        id: 'map-enhanced-polygon-fill',
                        type: 'fill',
                        source: 'map-widget-enhanced-report-data',
                        filter: ['==', '$type', 'Polygon'],
                        paint: {
                            'fill-color': '#1f6f78',
                            'fill-opacity': 0.18,
                            'fill-outline-color': '#1f6f78'
                        }
                    },
                    {
                        id: 'map-enhanced-line',
                        type: 'line',
                        source: 'map-widget-enhanced-report-data',
                        filter: ['==', '$type', 'LineString'],
                        paint: {
                            'line-color': '#1f6f78',
                            'line-width': 3
                        }
                    },
                    {
                        id: 'map-enhanced-point-halo',
                        type: 'circle',
                        source: 'map-widget-enhanced-report-data',
                        filter: ['==', '$type', 'Point'],
                        paint: {
                            'circle-radius': 6,
                            'circle-color': '#ffffff'
                        }
                    },
                    {
                        id: 'map-enhanced-point',
                        type: 'circle',
                        source: 'map-widget-enhanced-report-data',
                        filter: ['==', '$type', 'Point'],
                        paint: {
                            'circle-radius': 4,
                            'circle-color': '#1f6f78'
                        }
                    },
                    {
                        id: 'map-enhanced-pin-halo',
                        type: 'circle',
                        source: 'map-widget-enhanced-report-pin',
                        paint: {
                            'circle-radius': 8,
                            'circle-color': '#ffffff',
                            'circle-opacity': 0.95
                        }
                    },
                    {
                        id: 'map-enhanced-pin',
                        type: 'circle',
                        source: 'map-widget-enhanced-report-pin',
                        paint: {
                            'circle-radius': 5,
                            'circle-color': '#d84b2a',
                            'circle-opacity': 0.95
                        }
                    }
                ])
            };

            return style;
        });

        this.zoomReportMapToData = function() {
            if (!self.reportMap || !self.hasReportGeometry()) {
                return;
            }

            var bounds = geojsonExtent(self.reportFeatureCollection());
            self.reportMap.fitBounds(bounds, {
                padding: self.reportMapPadding,
                maxZoom: self.reportMapMaxZoom,
                duration: 0
            });
        };

        this.updateReportMapData = function() {
            if (!self.reportMap || !self.reportMap.getStyle()) {
                return;
            }

            var dataSource = self.reportMap.getSource('map-widget-enhanced-report-data');
            var pinSource = self.reportMap.getSource('map-widget-enhanced-report-pin');

            if (dataSource) {
                dataSource.setData(self.reportFeatureCollection());
            }
            if (pinSource) {
                pinSource.setData(self.reportPinFeatureCollection());
            }
        };

        this.setupReportMap = function(map) {
            self.reportMap = map;

            if (!map._enhancedNavControlAdded) {
                require(['mapbox-gl'], function(MapboxGl) {
                    if (!map._enhancedNavControlAdded) {
                        map.addControl(new MapboxGl.NavigationControl(), 'top-right');
                        map._enhancedNavControlAdded = true;
                    }
                });
            }

            var initializeMap = function() {
                self.updateReportMapData();
                self.zoomReportMapToData();
                // Force resize in case map was initialized while hidden
                setTimeout(function() {
                    map.resize();
                }, 100);

                // Keep map responsive as the browser window resizes
                if (window.ResizeObserver && !map._enhancedResizeObserver) {
                    map._enhancedResizeObserver = new ResizeObserver(function() {
                        map.resize();
                    });
                    map._enhancedResizeObserver.observe(map.getContainer());
                }
            };

            if (map.loaded()) {
                initializeMap();
            } else {
                map.on('load', initializeMap);
            }
        };

        this.reportFeatureCollection.subscribe(function() {
            self.updateReportMapData();
            self.zoomReportMapToData();
        });

        this.reportPinFeatureCollection.subscribe(function() {
            self.updateReportMapData();
        });

        if (ko.isObservable(this.value)) {
            this.value.subscribe(function() {
                self.updateReportMapData();
                self.zoomReportMapToData();
            });
        }
    };

    ko.components.register('map-widget-enhanced', {
        viewModel: EnhancedMapViewModel,
        template: mapEnhancedTemplate,
    });

    return EnhancedMapViewModel;
});
