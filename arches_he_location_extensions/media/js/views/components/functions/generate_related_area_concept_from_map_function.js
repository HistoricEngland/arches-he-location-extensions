define(['knockout',
        'knockout-mapping',
        'underscore',
        'views/list',
        'viewmodels/function',
        'bindings/chosen',
        'templates/views/components/functions/generate_related_area_concept_from_map_function.htm'],
function (ko, koMapping, _, ListView, FunctionViewModel, chosen, generateRelatedAreaConceptTemplate) {
    return ko.components.register('views/components/functions/generate_related_area_concept_from_map_function', {
        viewModel: function(params) {
            try{
                FunctionViewModel.apply(this, arguments);
                console.log("Running generate_related_area_concept_from_map_function")
                var self = this;
                this.nodesGeoJSON = ko.observableArray();
                this.nodesRelatedArea = ko.observableArray();
                this.nodesRelatedAreaType = ko.observableArray();
                this.nodesRelatedArea_enabled = ko.observable(false);
                this.nodesRelatedAreaType_enabled = ko.observable(false);

                this.geojson_input_node = params.config.geojson_input_node;
                this.relatedarea_name_output_node = params.config.relatedarea_name_output_node;
                this.relatedareatype_output_node = params.config.relatedareatype_output_node;
                this.triggering_nodegroups = params.config.triggering_nodegroups;
                this.webservice = params.config.webservice;
                this.geojson_parentnodegroupid = ""

                this.refresh_relatedarea_options = function(geojson_nodegroupid){

                    self.nodesRelatedArea.removeAll()
                    self.nodesRelatedAreaType.removeAll()
                    self.geojson_parentnodegroupid = ""

                    if (geojson_nodegroupid == null || geojson_nodegroupid == ""){
                        //self.relatedarea_name_output_node = "";
                        //self.relatedareatype_output_node = "";
                        self.nodesRelatedAreaType_enabled(false);
                        self.nodesRelatedArea_enabled(false);
                        return;
                    }

                    self.graph.nodegroups.forEach(function(nodegroup) {
                        if (nodegroup.nodegroupid == geojson_nodegroupid){
                            self.geojson_parentnodegroupid = nodegroup.parentnodegroup_id;
                        }
                    });

                    console.log("refresh_relatedarea_options: geojson_nodegroupid=", geojson_nodegroupid, "geojson_parentnodegroupid=", self.geojson_parentnodegroupid);

                    // If we've failed to get a parentNGid then there is an issue!
                    if (self.geojson_parentnodegroupid == null || self.geojson_parentnodegroupid == "") return;

                    self.nodesRelatedAreaType_enabled(true);
                    self.nodesRelatedArea_enabled(true);

                    // Include the parent nodegroup itself plus all its direct children (siblings of the GeoJSON nodegroup)
                    valid_nodegroupids = [self.geojson_parentnodegroupid];
                    self.graph.nodegroups.forEach(function(nodegroup) {
                        if (nodegroup.parentnodegroup_id == self.geojson_parentnodegroupid){
                            //nodegroup sibling found
                            valid_nodegroupids.push(nodegroup.nodegroupid);
                        }
                    });

                    console.log("refresh_relatedarea_options: valid_nodegroupids=", valid_nodegroupids);

                    self.graph.nodes.forEach(function(node) {

                        if(valid_nodegroupids.includes(node.nodegroup_id)){
                            console.log("refresh_relatedarea_options: candidate node", node.name, "datatype=", node.datatype, "nodegroup_id=", node.nodegroup_id);
                            //Related Area and Related Area Type = concept
                            if (node.datatype == 'concept'){
                                self.nodesRelatedArea.push(node);
                                self.nodesRelatedAreaType.push(node);
                            }
                        }

                    }, this);

                    window.setTimeout(function(){ $("select[data-bind^=chosen]").trigger("chosen:updated"); }, 100);

                }

                // Subscription.
                // Single node subscription. (They may want point/line/polygon in which case we'll need two more.)
                this.geojson_input_node.subscribe(function(geo_node_id){

                    if (geo_node_id != null && geo_node_id != "")
                    {
                        _.each(self.nodesGeoJSON(),function(node){
                            if (node.datatype == "geojson-feature-collection"){
                                if (geo_node_id === node.nodeid){
                                    self.triggering_nodegroups.push(node.nodegroup_id);
                                    params.config.geojson_input_nodegroup = node.nodegroup_id;
                                    console.log("geojson_input_nodegroup",self.geojson_input_nodegroup);

                                    self.refresh_relatedarea_options(node.nodegroup_id);
                                }
                            }
                        });
                    }
                    else{
                        self.triggering_nodegroups.removeAll();
                        params.config.geojson_input_nodegroup = '';
                        self.refresh_relatedarea_options(null);

                    }
                });

                this.relatedarea_name_output_node.subscribe(function(o_n){
                    console.log('Related Area Name node id:', o_n);
                    _.each(self.nodesRelatedArea(),function(node){
                        if (node.datatype !== "semantic"){
                            if (o_n === node.nodeid){
                                params.config.relatedarea_name_output_nodegroup = node.nodegroup_id;
                                console.log("relatedarea_name_output_nodegroup",self.relatedarea_name_output_nodegroup);
                            }
                        }
                    })
                })

                this.relatedareatype_output_node.subscribe(function(o_n){
                    console.log('Related Area Type node id:', o_n);
                    _.each(self.nodesRelatedAreaType(),function(node){
                        if (node.datatype !== "semantic"){
                            if (o_n === node.nodeid){
                                params.config.relatedareatype_output_nodegroup = node.nodegroup_id;
                                console.log("relatedareatype_output_nodegroup",self.relatedareatype_output_nodegroup);
                            }
                        }
                    })
                })

                this.webservice.subscribe(function(o_n){
                    console.log('Web Service:', o_n);
                    params.config.webservice = self.webservice();
                    console.log("Web Service: ",self.webservice());
                })

                if(this.relatedarea_name_output_node() != ""){
                    this.nodesRelatedArea_enabled(true);
                }
                if(this.relatedareatype_output_node() != ""){
                    this.nodesRelatedAreaType_enabled(true);
                }

                this.graph.nodes.forEach(function (node) {
                    //all the nodes selected need to be in a nodegroup that shares the same parent nodegroup.
                    if (node.datatype == 'geojson-feature-collection'){
                        self.nodesGeoJSON.push(node);
                    }
                }, this);

                if(params.config.geojson_input_nodegroup() != ""){
                    this.refresh_relatedarea_options(params.config.geojson_input_nodegroup());
                }


                window.setTimeout(function(){$("select[data-bind^=chosen]").trigger("chosen:updated")}, 300);
            }
            catch(err){
                console.error(err.message);
            }
        },
        template: generateRelatedAreaConceptTemplate
    });
})