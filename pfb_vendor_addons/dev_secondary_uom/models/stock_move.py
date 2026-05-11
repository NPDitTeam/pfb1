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

class stock_move(models.Model):
    _inherit = "stock.move"
    
    uom_category_id = fields.Many2one('uom.category', related='product_uom.category_id', string='UOM Category')
    second_uom_id = fields.Many2one('uom.uom',string="Secondary UOM")
    second_uom_qty = fields.Float('Secondary Qty')
    second_uom_done_qty = fields.Float('Secondary Done Qty')
    
    
    @api.onchange('quantity_done','product_uom_qty')
    def onchange_product_quantity(self):
        if self.product_id and not self.second_uom_id:
            self.second_uom_id = self.product_id.second_uom_id and self.product_id.second_uom_id.id or False
        if self.second_uom_id and self.product_uom:
            self.second_uom_qty = self.product_uom._compute_quantity(self.product_uom_qty, self.second_uom_id)
            self.second_uom_done_qty = self.product_uom._compute_quantity(self.quantity_done, self.second_uom_id)
    
    @api.onchange('product_id')
    def _onchange_dev_product_id(self):
        if self.product_id:
            self.second_uom_id = self.product_id.second_uom_id and self.product_id.second_uom_id.id or False
            if self.second_uom_id:
                self.second_uom_qty = self.product_uom._compute_quantity(self.product_uom_qty, self.second_uom_id)

    @api.onchange('second_uom_done_qty','second_uom_id')
    def onchange_second_done_quantity(self):
        if self.second_uom_id and self.product_uom:
            self.quantity_done = self.second_uom_id._compute_quantity(self.second_uom_done_qty, self.product_uom)
            
    
    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        res = super(stock_move,self)._prepare_move_line_vals(quantity,reserved_quant)
        if res.get('product_uom_id') and res.get('product_uom_qty') and self.second_uom_id:
            uom_id = self.env['uom.uom'].browse(res.get('product_uom_id'))
            second_uom_qty = uom_id._compute_quantity(res.get('product_uom_qty'), self.second_uom_id)
            res.update({
                'second_uom_id':self.second_uom_id and self.second_uom_id.id or False,
                'second_uom_qty':second_uom_qty,
            })
        return res

class stock_move_line(models.Model):
    _inherit = 'stock.move.line'    
    
    uom_category_id = fields.Many2one('uom.category', related='product_uom_id.category_id', string='UOM Category')
    second_uom_id = fields.Many2one('uom.uom',string="Secondary UOM")
    second_uom_qty = fields.Float('Secondary Qty')
    second_uom_done_qty = fields.Float('Secondary Done Qty')
    
    
    @api.onchange('product_uom_qty','qty_done','product_uom_id')
    def _onchange_product_qunatity(self):
        if self.product_id and not self.second_uom_id:
            self.second_uom_id = self.product_id.second_uom_id and self.product_id.second_uom_id.id or False
        if self.second_uom_id and self.product_uom_id:
            self.second_uom_qty = self.product_uom_id._compute_quantity(self.product_uom_qty, self.second_uom_id)
            self.second_uom_done_qty = self.product_uom_id._compute_quantity(self.qty_done, self.second_uom_id)
    
    
    @api.onchange('second_uom_qty','second_uom_done_qty','second_uom_id')
    def _onchange_product_second_quantity(self):
        if self.second_uom_id and self.product_uom_id:
            self.product_uom_qty = self.second_uom_id._compute_quantity(self.second_uom_qty, self.product_uom_id)
            self.qty_done = self.second_uom_id._compute_quantity(self.second_uom_done_qty, self.product_uom_id)
    

class stock_rule(models.Model):
    _inherit = 'stock.rule'
    
    
    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_id, name, origin, values, group_id):
        res = super(stock_rule,self)._get_stock_move_values(product_id, product_qty, product_uom, location_id, name, origin, values, group_id)
        if group_id.get('sale_line_id'):
            line = self.env['sale.order.line'].browse(group_id.get('sale_line_id'))
            if line and line.second_uom_id:
                res.update({
                    'second_uom_id':line.second_uom_id and line.second_uom_id.id or False,
                    'second_uom_qty':line.second_uom_qty
                })
        return res
        
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
