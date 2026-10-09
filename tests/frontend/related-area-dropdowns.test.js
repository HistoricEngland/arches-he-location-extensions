import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";

const require = createRequire(import.meta.url);
const applicationPath = resolve("arches_he_location_extensions");
let container;

beforeAll(() => {
    require("select-woo/dist/js/selectWoo.full.js")(window, $);
    runInNewContext(
        readFileSync(
            require.resolve("arches/arches/app/media/js/bindings/select2-query.js"),
            "utf8",
        ),
        {
            define: (dependencies, factory) => factory($, ko, _),
            document,
            window,
        },
    );
});

afterEach(async () => {
    // SelectWoo's global keyboard handlers are not removed by destroy.
    $(document).off("keydown");
    if (container) {
        await new Promise((resolve) => window.setTimeout(resolve, 10));
        ko.removeNode(container);
        container = undefined;
    }
});

async function renderPanel(templateName) {
    const template = readFileSync(
        resolve(applicationPath, "templates/views/components/functions", templateName),
        "utf8",
    )
        .replace(/{% trans "([^"]+)" %}/g, "$1")
        .replace(/{% load i18n %}/g, "");
    const model = {
        nodesGeoJSON: ko.observableArray([
            { nodeid: "geojson", name: "Geospatial Coordinates" },
        ]),
        nodesRelatedArea: ko.observableArray([
            { nodeid: "area-name", name: "Area Name" },
        ]),
        nodesRelatedAreaType: ko.observableArray([
            { nodeid: "area-type", name: "Area Type" },
        ]),
        geojson_input_node: ko.observable("geojson"),
        relatedarea_name_output_node: ko.observable("area-name"),
        relatedareatype_output_node: ko.observable("area-type"),
        nodesRelatedArea_enabled: ko.observable(true),
        nodesRelatedAreaType_enabled: ko.observable(true),
        webservice: ko.observable(""),
    };
    container = document.createElement("div");
    container.innerHTML = template;
    document.body.appendChild(container);
    ko.applyBindings(model, container);
    await new Promise((resolve) => $(document).ready(resolve));
    return model;
}

function combobox(selectId) {
    return container.querySelector(`#${selectId}`).nextElementSibling
        .querySelector('[role="combobox"]');
}

describe.each([
    "generate_related_area_from_map_function",
    "generate_related_area_concept_from_map_function",
])("%s", (component) => {
    it("loads the SelectWoo binding without Chosen refresh timers", () => {
        const view = readFileSync(
            resolve(applicationPath, "media/js/views/components/functions", `${component}.js`),
            "utf8",
        );
        expect(view).toContain("'bindings/select2-query'");
        expect(view).not.toMatch(/chosen|setTimeout/);
    });

    it("exposes each label, selected value, and state on a focusable combobox", async () => {
        await renderPanel(`${component}.htm`);
        for (const [id, label, value] of [
            ["geojson-node-select", "GeoJSON Node", "Geospatial Coordinates"],
            ["related-area-name-select", "Related Area Name Node", "Area Name"],
            ["related-area-type-select", "Related Area Type Node", "Area Type"],
        ]) {
            const control = combobox(id);
            expect(control.getAttribute("aria-label")).toBe(`${label}, ${value}`);
            expect(control.textContent).toContain(value);
            expect(control.getAttribute("tabindex")).toBe("0");
            expect(control.getAttribute("aria-expanded")).toBe("false");
            expect(container.querySelector(`#${id}`).disabled).toBe(false);
        }
    });

    it("keeps selected values in sync in both directions", async () => {
        const model = await renderPanel(`${component}.htm`);
        model.nodesRelatedArea.push({ nodeid: "other-area", name: "Other Area" });
        model.relatedarea_name_output_node("other-area");
        await vi.waitFor(() => {
            expect(combobox("related-area-name-select").textContent).toContain("Other Area");
        });
        $("#related-area-name-select").val("area-name").trigger("change");
        await vi.waitFor(() => {
            expect(model.relatedarea_name_output_node()).toBe("area-name");
            expect(combobox("related-area-name-select").textContent).toContain("Area Name");
        });
    });

    it("supports keyboard opening and closing with an announced expanded state", async () => {
        await renderPanel(`${component}.htm`);
        const control = combobox("geojson-node-select");
        control.focus();
        $(control).trigger($.Event("keydown", { which: 40 }));
        expect(control.getAttribute("aria-expanded")).toBe("true");
        expect(document.querySelector('[role="listbox"]').textContent)
            .toContain("Geospatial Coordinates");
        $(".select2-search__field").trigger($.Event("keydown", { which: 27 }));
        expect(control.getAttribute("aria-expanded")).toBe("false");
    });

    it("updates options and disabled states when related nodes are unavailable", async () => {
        const model = await renderPanel(`${component}.htm`);
        model.nodesRelatedArea_enabled(false);
        model.nodesRelatedAreaType_enabled(false);
        model.nodesRelatedArea.removeAll();
        model.nodesRelatedAreaType.removeAll();
        await vi.waitFor(() => {
            for (const id of ["related-area-name-select", "related-area-type-select"]) {
                expect(container.querySelector(`#${id}`).disabled).toBe(true);
                expect(combobox(id).getAttribute("tabindex")).toBe("-1");
                expect(container.querySelector(`#${id}`).options.length).toBe(0);
            }
        });
        model.nodesRelatedArea.push({ nodeid: "area-name", name: "Area Name" });
        model.nodesRelatedArea_enabled(true);
        await vi.waitFor(() => {
            expect(container.querySelector("#related-area-name-select").disabled).toBe(false);
            expect(combobox("related-area-name-select").getAttribute("tabindex")).toBe("0");
            expect(combobox("related-area-name-select").textContent).toContain("Area Name");
            expect(model.relatedarea_name_output_node()).toBe("area-name");
        });
    });
});
