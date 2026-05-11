odoo.define('pways_transportor_management.ShipmentDashboard', function (require) {
    'use strict';

    var AbstractAction = require('web.AbstractAction');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var web_client = require('web.web_client');
    var session = require('web.session');
    var _t = core._t;
    var QWeb = core.qweb;
    var self = this;
    var ShipmentDashboard = AbstractAction.extend({
        contentTemplate: 'ShipmentDashboard',
        
    init: function(parent, options) {
        this._super(parent, options);
        this.transporter = 0;
        this.total_shipment = 0;
        this.total_draft = 0;
        this.total_ready = 0;
        this.total_halt = 0;
        this.total_done = 0;

    },
    fetch_data: function () {
        var self = this;
        var def1 =  this._rpc({
            model: 'stock.picking.transport.info',
            method: 'get_transport_data',
            args: [],
        }).then(function(result) {
            self.transporter = result.transporter
            self.total_shipment = result.total_shipment
            self.total_draft = result.total_draft
            self.total_ready = result.total_ready
            self.total_halt = result.total_halt
            self.total_done = result.total_done
        });
        var def2 =  this._rpc({
            model: 'stock.picking.transport.info',
            method: 'transport_route_data',
            args: [],
        }).then(function(result) {
            self.transport_route_data = result
        });

        return $.when(def1,def2);
    },
    willStart: function() {
        var self = this;
        return $.when(ajax.loadLibs(this), this._super()).then(function() {
            return self.fetch_data();
        });
    },
    start: function() {
        var self = this;
        return this._super().then(function() {
            self.$('.o_Shipment_dashboard').html(QWeb.render('ShipmentData', {
                'transporter': self.transporter,
                'total_shipment': self.total_shipment,
                'total_draft': self.total_draft,
                'total_ready': self.total_ready,
                'total_halt': self.total_halt,
                'total_done': self.total_done,
                'transport_route_data' : self.transport_route_data,
            }));
        });
    },
    });

    core.action_registry.add('shipment_dashboard', ShipmentDashboard);
    return ShipmentDashboard;
});
