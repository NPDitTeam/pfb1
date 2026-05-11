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

class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'
    
    def process(self):
        res = super(StockImmediateTransfer,self).process()
        print ("=====call process============")
        for picking in self.pick_ids:
            for move in picking.move_lines.filtered(lambda m: m.state not in ['cancel']):
                move.onchange_product_quantity()
                for m_line in move.move_line_ids:
                    m_line._onchange_product_qunatity()
        return res
        
        
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
