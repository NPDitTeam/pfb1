# -*- coding: utf-8 -*-

from odoo import models, fields

class AccountInvoice(models.Model):
    _inherit = 'account.move'
    
    transporter_id = fields.Many2one('res.partner', string="Transporter")

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    transporter_id = fields.Many2one('res.partner', string='Transporter')
    driver_id = fields.Many2one('res.partner', 'Driver', tracking=True, help='Driver of the vehicle', copy=False, invisible=True)
    transport_driver_id = fields.Many2one('transport.driver', 'Driver', tracking=True, help='Driver of the vehicle', copy=False)
