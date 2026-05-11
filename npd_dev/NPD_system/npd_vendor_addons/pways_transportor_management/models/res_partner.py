# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class Partner(models.Model):
    _inherit = 'res.partner'

    transporter = fields.Boolean(copy=False, onchange=1)
    vehicle_count = fields.Integer(string='Vehicles', store=True, compute = '_vehicle_count')
    vehicle_ids = fields.One2many('fleet.vehicle', 'transporter_id', string='Vehicles', store=True)
    trans_type = fields.Selection([('sale','Sale'),('picking','Picking'),('manual','Manual')], default='sale', string='Shipment From')
    route = fields.Many2many('stock.transporter.route' , string='Route')
    driver_id = fields.Many2many('transport.driver', string= "Driver")
    vehicle = fields.Many2many('fleet.vehicle', string='Vehicles')
    rate = fields.Float()

    @api.depends('vehicle_ids')
    def _vehicle_count(self):
        for rec in self:
            rec.vehicle_count  = len(rec.vehicle_ids)
 
    def show_vehicle(self):
        return {
            'name': _('Vehicles'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'fleet.vehicle',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.vehicle_ids.ids)],
        }

    @api.model
    def get_partner_data(self):
        return 0

          
class TransportDriver(models.Model):
    _name = 'transport.driver'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']


    name = fields.Char(string= 'Name' , required=True)
    phone = fields.Char(string='Phone No')
    email = fields.Char(string='Email')
    licence_id = fields.Char(string='Licence No')
    licence_type = fields.Selection([("ll","Learner's driving license"),("pl"," Permanent driving license"),("cl","Commercial driving license"),("in","International driving permi")],string='Licence Type')
    valid_from = fields.Date(string='Valid From')
    valid_to = fields.Date(string='Expried Date')
    date_exp = fields.Char(compute="_compute_date")

    @api.depends('valid_to')
    def _compute_date(self):
        print("self....",self)
        for rec in self:
            # today= date.today()
            if rec.valid_to:
                rec.date_exp = rec.valid_to.year-rec.valid_from.year
            else:
                rec.date_exp = 0