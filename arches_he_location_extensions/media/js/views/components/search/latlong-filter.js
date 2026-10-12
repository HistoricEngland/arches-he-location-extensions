define([
    'knockout',
    'views/components/search/base-filter',
    'templates/views/components/search/latlong-filter.htm',
], function(ko, BaseFilter, latlongFilterTemplate) {
    const componentName = 'latlong-filter';

    // null means the field has not been edited yet, so no error is shown
    const rangeError = function(value, label, min, max) {
        if (value === null || value === undefined) { return ''; }
        const entry = String(value).trim();
        if (entry === '') { return label + ' is required'; }
        const number = Number(entry);
        if (!isFinite(number)) { return label + ' must be a number'; }
        if (number < min || number > max) {
            return label + ' must be between ' + min + ' and ' + max;
        }
        return '';
    };

    const viewModel = BaseFilter.extend({
        initialize: function(options) {
            options.name = 'LatLong Filter';
            BaseFilter.prototype.initialize.call(this, options);

            this.filter = {
                longitude: ko.observable(null),
                latitude: ko.observable(null),
                buffer: ko.observable(0),
                inverted: ko.observable(false)
            };

            this.longitudeError = ko.pureComputed(function() {
                return rangeError(this.filter.longitude(), 'Longitude (X)', -180, 180);
            }, this);

            this.latitudeError = ko.pureComputed(function() {
                return rangeError(this.filter.latitude(), 'Latitude (Y)', -90, 90);
            }, this);

            this.bufferError = ko.pureComputed(function() {
                const value = this.filter.buffer();
                if (value === null || value === undefined) { return ''; }
                const entry = String(value).trim();
                if (entry === '') { return ''; }
                const number = Number(entry);
                if (!isFinite(number)) { return 'Buffer radius must be a number'; }
                if (number < 0) { return 'Buffer radius must be 0 or greater'; }
                return '';
            }, this);

            this.hasErrors = ko.pureComputed(function() {
                return !!(this.longitudeError() || this.latitudeError() || this.bufferError());
            }, this);

            // the filter only reaches the query once applied, but inverting the
            // term-filter tag afterwards must re-run the search
            this.applied = ko.observable(false);
            this.filter.inverted.subscribe(function() {
                if (this.applied()) { this.updateQuery(); }
            }, this);

            this.restoreState();
            this.searchFilterVms[componentName](this);
        },

        apply: function() {
            if (this.filter.longitude() === null) { this.filter.longitude(''); }
            if (this.filter.latitude() === null) { this.filter.latitude(''); }
            if (this.hasErrors()) { return; }

            this.applied(true);
            this.addTag();
            this.updateQuery();
        },

        addTag: function() {
            // term-filter ignores a repeated tag, and keeps our inverted observable
            this.getFilterByType('term-filter-type').addTag(this.name, this.name, this.filter.inverted);
        },

        updateQuery: function() {
            const queryObj = this.query();
            if (this.applied() && !this.hasErrors()) {
                queryObj[componentName] = JSON.stringify({
                    longitude: Number(this.filter.longitude()),
                    latitude: Number(this.filter.latitude()),
                    buffer: Number(this.filter.buffer()) || 0,
                    inverted: this.filter.inverted()
                });
            } else {
                delete queryObj[componentName];
            }
            this.query(queryObj);
        },

        restoreState: function() {
            const query = this.query();
            if (componentName in query) {
                const value = JSON.parse(query[componentName]);
                this.filter.longitude(value.longitude);
                this.filter.latitude(value.latitude);
                this.filter.buffer(value.buffer);
                this.filter.inverted(!!value.inverted);
                this.applied(true);
                this.addTag();
            }
        },

        clear: function() {
            this.filter.longitude(null);
            this.filter.latitude(null);
            this.filter.buffer(0);
            this.filter.inverted(false);
            this.applied(false);
            this.getFilterByType('term-filter-type').removeTag(this.name);
            this.updateQuery();
        }
    });

    return ko.components.register(componentName, {
        viewModel: viewModel,
        template: latlongFilterTemplate,
    });
});
