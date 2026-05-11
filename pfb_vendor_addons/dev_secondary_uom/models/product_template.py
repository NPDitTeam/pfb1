# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import models, fields, api, _

class product_template(models.Model):
    _inherit = "product.template"
    
    
    @api.depends('second_uom_id')
    def get_secondary_qty_available(self):
        for record in self:
            record.secondary_qty_available = record.qty_available
            if record.second_uom_id:
                record.secondary_qty_available = record.uom_id._compute_quantity(record.qty_available, record.second_uom_id)

    @api.depends('second_uom_id')
    def get_secondary_forcast(self):
        for record in self:
            record.secondary_forcast = record.virtual_available
            if record.second_uom_id:
                record.secondary_forcast = record.uom_id._compute_quantity(record.virtual_available, record.second_uom_id)
                
                
    
    uom_category_id = fields.Many2one('uom.category', related='uom_id.category_id', string='UOM Category')
    is_second_uom = fields.Boolean('Secondary UOM')
    second_uom_id = fields.Many2one('uom.uom',string="Secondary UOM")
    secondary_qty_available = fields.Float(string="Secondary Unit of Measure", compute='get_secondary_qty_available')
    secondary_forcast = fields.Float(string="Secondary Forcast", compute='get_secondary_forcast')
    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
