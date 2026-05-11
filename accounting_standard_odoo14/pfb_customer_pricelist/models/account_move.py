from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    customer_list = fields.Many2many(comodel_name='res.partner',string='customer list',compute='_get_customer_list')
    
    @api.depends('partner_id')
    def _get_customer_list(self):
        customer_ids = []
        for move in self:
            price_list = self.env['product.supplierinfo'].search(
                [
                    ('name', '=', move.partner_id.id),
                ]
            )    
            for list in price_list:
                if list.customer_id and list.customer_id.id not in customer_ids:
                    customer_ids.append(list.customer_id.id)

            if customer_ids:
                move.customer_list = customer_ids
            else:
                move.customer_list = None

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    customer_id = fields.Many2one('res.partner', string='Customer ')

    @api.onchange('customer_id','product_id')
    def onchange_domain_customer_id(self):
        if self.move_id.move_type == 'in_invoice':
            price_list = self.env['product.supplierinfo'].search(
                [ 
                    # ('name', '=', self.move_id.partner_id.id),
                    ('customer_id', '=', self.customer_id.id),
                    ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id),
                ]
                , limit=1
            )
            if price_list:
                self.quantity = price_list.min_qty
                self.price_unit = price_list.price