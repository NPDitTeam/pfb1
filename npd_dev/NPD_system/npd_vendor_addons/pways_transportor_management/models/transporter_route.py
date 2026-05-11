# -*- coding: utf-8 -*-

from odoo import fields, models, api

class ShipmentType(models.Model):
    _name = 'shipment.type'

    name = fields.Char() 

class TransportLocation(models.Model):
    _name = 'transport.location'

    name =fields.Char(string='Name', required = True)
    phone_no = fields.Char()
    email = fields.Char()
    partner_id = fields.Many2one('res.partner', string="Select Store", domain="[['category_id.name','ilike','store']]")
    address = fields.Text(string="Store Address", compute="o_address_format")
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Char()
    zip = fields.Char()
    country_id = fields.Char() 

class StockRouteLocation(models.Model):
    _name = 'stock.route.location'
   
    name = fields.Char(string='Name', required = True)

class StockTransporterRoute(models.Model):
    _name = 'stock.transporter.route'

    name = fields.Char(string='Name', required=True)
    transporter_id = fields.Many2one('res.partner', string='Transporter', required=True)
    route_line_ids = fields.One2many('stock.transporter.route.line', 'route_id', string='Shipment Route Lines')

class StockTransporterRouteLine(models.Model):
    _name = 'stock.transporter.route.line'

    transporter_id = fields.Many2one('res.partner', string='Transporter')
    route_id = fields.Many2one('stock.transporter.route', string='Shipment Route')
    source_location = fields.Many2one('transport.location', string='Source', required=True)
    destination_location = fields.Many2one('transport.location', string='Destination',required=True)
    distance = fields.Float(string='Distance', required=True)
    hour = fields.Float(string='Hours', required=True)
