# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################
#

from odoo import api, fields, models, tools


class PurchaseReport(models.Model):
    _inherit = "purchase.report"
    
    second_uom_id = fields.Many2one('uom.uom', 'Secondary UOM', readonly=True)
    second_uom_qty = fields.Float('Secondary Quantity', readonly=True)
    second_price = fields.Float('Second Price', readonly=True)

    
    def _select(self):
        query = ", t.second_uom_id as second_uom_id, \
                    sum(l.second_price / COALESCE(NULLIF(cr.rate, 0), 1.0) * l.second_uom_qty)::decimal(16,2) as second_price, \
                    sum(l.second_uom_qty/ u3.factor*u4.factor) as second_uom_qty"
        return super(PurchaseReport, self)._select() + query
        
    def _from(self):
        query = '''left join uom_uom u3 on (u3.id=l.second_uom_id)
                left join uom_uom u4 on (u4.id=t.second_uom_id)'''
        return super(PurchaseReport, self)._from() + query
        
        
    def _group_by(self):
        return super(PurchaseReport, self)._group_by() + ", t.second_uom_id"

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
