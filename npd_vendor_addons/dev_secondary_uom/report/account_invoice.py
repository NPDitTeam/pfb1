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


class account_invoice(models.Model):
    _inherit = "account.invoice.report"
    
    second_uom_id = fields.Many2one('uom.uom', 'Secondary UOM', readonly=True)
    second_uom_qty = fields.Float('Secondary Quantity', readonly=True)
    second_price = fields.Float('Second Price', readonly=True)
    
    
    def _select(self):
        query = ", sub.second_uom_id,sub.second_price, \
                    sub.second_uom_qty"
        return super(account_invoice, self)._select() + query
        
    def _from(self):
        query = '''LEFT JOIN uom_uom u3 ON u3.id = ail.second_uom_id
                LEFT JOIN uom_uom u4 ON u4.id = pt.second_uom_id '''
        return super(account_invoice, self)._from() + query
        
        
    def _sub_select(self):
        query = ", pt.second_uom_id as second_uom_id, \
                    SUM(ail.second_price * invoice_type.sign) AS second_price, \
                    sum((invoice_type.sign_qty * ail.second_uom_qty) / COALESCE(u3.factor,1) * COALESCE(u4.factor,1)) as second_uom_qty"
        return super(account_invoice, self)._sub_select() + query
    
    def _group_by(self):
        return super(account_invoice, self)._group_by() + ", pt.second_uom_id"
        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
