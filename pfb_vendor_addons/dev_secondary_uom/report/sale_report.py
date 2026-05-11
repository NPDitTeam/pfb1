# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    second_uom_id = fields.Many2one('uom.uom', 'Secondary UOM', readonly=True)
    second_uom_qty = fields.Float('Secondary Quantity', readonly=True)
    second_price = fields.Float('Second price', readonly=True)


    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        fields.update({
            'second_uom_id':', t.second_uom_id as second_uom_id',
            'second_uom_qty':', sum(l.second_uom_qty / u3.factor * u4.factor) as second_uom_qty',
            'second_price':', sum(l.second_price / CASE COALESCE(s.currency_rate, 0) WHEN 0 THEN 1.0 ELSE s.currency_rate END) as second_price',
        })
        from_clause = '''left join uom_uom u3 on (u3.id=l.second_uom_id)
                    left join uom_uom u4 on (u4.id=t.second_uom_id)'''
                    
                    
        groupby = groupby + ', t.second_uom_id'
        return super(SaleReport, self)._query(with_clause, fields, groupby, from_clause)
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
