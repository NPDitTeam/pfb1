# -*- coding: utf-8 -*-

from odoo import models, fields, api , _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    @api.depends('picking_transport_ids')
    def _picking_transport_count(self):
        for rec in self:
            rec.picking_transport_count = len(rec.picking_transport_ids)

    transporter_id = fields.Many2one('res.partner',string="Transporter")
    lr_number = fields.Char(string="LR Number", copy=True, required=False)
    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle")
    vehicle_driver = fields.Many2one('transport.driver', string="Vehicle Driver", related='vehicle_id.transport_driver_id')
    no_of_parcel = fields.Float(string="No of Parcels", copy=True, required=False)
    picking_transport_ids = fields.One2many('stock.picking.transport.info', 'delivery_id', string="Picking Transport")
    picking_transport_count = fields.Integer(compute = '_picking_transport_count', store=True)
    picking_route_ids = fields.One2many('stock.picking.route','delivery_id', string='Shipment Route')
    transporter_route_id = fields.Many2one('stock.transporter.route', string='Shipment Route')
    transport_date = fields.Datetime(string='Transport Date', default=fields.Datetime.now())
    number_of_packages = fields.Integer(string='Number of Packages',copy=False)
    picking_type = fields.Many2one('shipment.type', string='Shipment Type')
    pick_date = fields.Date(string='Pickup Date')
    arrive_date = fields.Date(string='Arrival Date')
    create_trans = fields.Boolean(copy=False)

    def compute_transporter_route(self,info_create):
        if self.picking_route_ids:
            self.picking_route_ids.unlink()
        for rec in self:
            transporter_route_id = rec.transporter_route_id or rec.sale_id.transporter_route_id
            for val in transporter_route_id.route_line_ids:
                picking_route_vals = {
                    'source_location': val.source_location.id,
                    'destination_location' : val.destination_location.id,
                    'distance' : val.distance,
                    'hour' : val.hour,
                    'delivery_id' : rec.id,
                    'delivery_route_id': info_create and info_create.id
                }
                self.env['stock.picking.route'].create(picking_route_vals)

    def create_transport_record(self, transporter_id):
        if transporter_id.trans_type in ('sale', 'picking'):
            entry_ids = self.env['stock.picking.transport.info'].search([('delivery_id', '=', self.id)])
            if not entry_ids:
                for rec in self:
                    vals = {
                        'saleorder_id': rec.sale_id.id,
                        'lr_number' : rec.lr_number,
                        'transporter_id': transporter_id.id,
                        'vehicle_id' : rec.vehicle_id.id,
                        'vehicle_driver' : rec.vehicle_driver.id,
                        'transport_date' : fields.Date.today(),
                        'delivery_id' : rec.id,
                        'customer_id' : rec.partner_id.id,
                        'destination_id' : rec.location_dest_id.id,
                        'carrier_id' : rec.carrier_id.id,
                        'carrier_tracking_ref' : rec.carrier_tracking_ref,
                        'weight' : rec.weight,
                        'shipping_weight' : rec.shipping_weight,
                        'number_of_packages' : rec.number_of_packages,
                        'no_of_parcel' :rec.no_of_parcel,
                        'user_id' : self.env.user.id,
                        'transport_date' : rec.transport_date,
                    }
                    info_create = self.env['stock.picking.transport.info'].create(vals)
                    rec.compute_transporter_route(info_create)
        return True

    def button_validate(self):
        if self.transporter_id and not self.create_trans:
            raise UserError("Please update shipment information")
        res = super(StockPicking, self).button_validate()
        self.create_transport_record(self.transporter_id)
        return res

    def show_picking_transport(self):
        for rec in self:
            res = self.env.ref('pways_transportor_management.action_picking_transport_info')
            res = res.read()[0]
            res['domain'] = str([('id','in',rec.picking_transport_ids.ids)])
        return res

    def show_route_transport(self):
        for rec in self:
            res = self.env.ref('pways_transportor_management.action_transport_management_route')
            res = res.read()[0]
            res['domain'] = str([('id','in',rec.picking_transport_ids.ids)])
        return res

    def show_shipment_wizard(self):
        if self.transporter_id and self.transporter_id.trans_type == 'picking' and not self.create_trans:
            return {
                'name': _('Add Shipment Information'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.shipment.wizard',
                'type': 'ir.actions.act_window',
                'target':'new',
            }