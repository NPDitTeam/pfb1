# -*- coding: utf-8 -*-

from odoo import models, fields, api , _
from datetime import datetime
from odoo.exceptions import UserError


class Sale(models.Model):
    _inherit = 'sale.order'

    def _picking_transport_count(self):
        for rec in self:
            rec.picking_transport_count = len(rec.picking_ids.mapped('picking_transport_ids'))
   
    transporter_id = fields.Many2one('res.partner', string="Transporter")
    create_trans = fields.Boolean(copy=False)
    pick_date = fields.Date(string='Pickup Date', copy=False)
    arrive_date = fields.Date(string='Arrival Date',copy=False)
    picking_transport_count = fields.Integer(compute='_picking_transport_count')
    transporter_route_id = fields.Many2one('stock.transporter.route', string='Shipment Route',copy=False)
    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle", copy=False)
    vehicle_driver = fields.Many2one('transport.driver', string="Driver", copy=False)
    picking_type = fields.Many2one('shipment.type', string='Shipment Type', copy=False)

    def action_confirm(self):
        res = super(Sale, self).action_confirm()
        if self.transporter_id and self.transporter_id.trans_type == 'sale' and not self.create_trans:
            raise UserError("Please update shipment information")
        if self.picking_ids:
            fil_picking_ids = self.picking_ids.filtered(lambda x: x.state != 'cancel')
            fil_picking_ids.write({'transporter_id': self.transporter_id.id})
            if self.transporter_id.trans_type == 'sale' and fil_picking_ids:
                fil_picking_ids.create_transport_record(self.transporter_id)
                for pick in fil_picking_ids:
                    pick.write({
                        'transporter_route_id': self.transporter_route_id.id,
                        'vehicle_driver': self.vehicle_driver.id,
                        'vehicle_id': self.vehicle_id.id, 
                        'pick_date': self.pick_date,
                        'arrive_date':self.arrive_date,
                        'picking_type':self.picking_type.id,
                        'create_trans': True,
                    })
        return res

    def _prepare_invoice(self):
       res = super(Sale, self)._prepare_invoice()
       if self.transporter_id:
            vals = {'transporter_id': self.transporter_id.id}
            res.update(vals)
       return res

    def show_picking_transport(self):
        partner_ids = self.env['stock.picking.transport.info'].search([('saleorder_id','=', self.id)])
        return {
            'name': _('Shipment Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'stock.picking.transport.info',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in' , partner_ids.ids)],
        }

    def show_shipment_wizard(self):
        if self.transporter_id and self.transporter_id.trans_type == 'sale' and not self.create_trans:
            return {
                'name': _('Add Shipment Information'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.shipment.wizard',
                'type': 'ir.actions.act_window',
                'target':'new',
            }