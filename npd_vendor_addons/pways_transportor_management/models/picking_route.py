# -*- coding: utf-8 -*-

from odoo import fields,api, models
from datetime import datetime

class StockPickingRoute(models.Model):
    _name = 'stock.picking.route'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char(string='Number', readonly=True)
    source_location = fields.Many2one('transport.location', string='Source', required=True)
    destination_location = fields.Many2one('transport.location', string='Destination', required=True)
    distance = fields.Float(string='Distance(Km)', required=True)
    hour = fields.Float(string='Hours', required=True)
    status = fields.Selection([('start', 'Start'), ('onroute', 'On Route'),('halt', 'Halt'),('reach', 'Reached')],default='start')
    note = fields.Text(string='Notes')
    gps_tracking = fields.Char(string='Tracking No')
    delivery_id = fields.Many2one('stock.picking',string='Delivery')
    delivery_route_id = fields.Many2one('stock.picking.transport.info', string='Picking Transport Info')
    start_time = fields.Datetime(string="Start Time", default=datetime.now())
    end_time = fields.Datetime(string="End Time")
    state = fields.Selection([('start', 'Yet to Begin'),('onroute', 'On Route'),('halt', 'Stoped'),('reach', 'Reached')],
        default='start',
        track_visibility='onchange',
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            name = self.env['ir.sequence'].next_by_code('picking.transport.route.seq')
            val.update({'name': name})
        return super(StockPickingRoute, self).create(vals)
    
    def route_hold(self):
        self.write({'state': 'halt', 'status': 'halt'})

    def route_on_route(self):
        self.write({'state': 'onroute', 'status': 'onroute'})

    def route_reach(self):
        self.write({'state': 'reach', 'status': 'reach', 'end_time': datetime.now()})
