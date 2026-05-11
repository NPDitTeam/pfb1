from itertools import chain

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang


# class SaleAdvancePaymentInv(models.TransientModel):
#     _inherit = "sale.advance.payment.inv"
#
#
#     def _prepare_invoice_values(self, order, name, amount, so_line):
#         print('_prepare_invoice_values',order.pfb_so_type)
#
#         if order.pfb_so_type == 'rent':
#             invoice_vals = {
#                 'ref': order.client_order_ref,
#                 'move_type': 'out_invoice',
#                 'invoice_origin': order.name,
#                 'invoice_user_id': order.user_id.id,
#                 'narration': order.note,
#                 'partner_id': order.partner_invoice_id.id,
#                 'fiscal_position_id': (order.fiscal_position_id or order.fiscal_position_id.get_fiscal_position(order.partner_id.id)).id,
#                 'partner_shipping_id': order.partner_shipping_id.id,
#                 'currency_id': order.pricelist_id.currency_id.id,
#                 'payment_reference': order.reference,
#                 'invoice_payment_term_id': order.payment_term_id.id,
#                 'partner_bank_id': order.company_id.partner_id.bank_ids[:1].id,
#                 'team_id': order.team_id.id,
#                 'campaign_id': order.campaign_id.id,
#                 'medium_id': order.medium_id.id,
#                 'source_id': order.source_id.id,
#                 'pfb_so_type': order.pfb_so_type,
#                 'pfb_date_of_rent': order.pfb_date_of_rent,
#                 'pfb_objective_id': order.pfb_objective_id.id,
#                 'pfb_amount_insurance': order.pfb_amount_insurance,
#                 'pfb_dis_amount_insurance': order.pfb_dis_amount_insurance,
#                 'pfb_amount': order.pfb_amount,
#                 'invoice_line_ids': [(0, 0, {
#                     'name': name,
#                     'price_unit': amount,
#                     'quantity': 1.0,
#                     'product_id': self.product_id.id,
#                     'product_uom_id': so_line.product_uom.id,
#                     'tax_ids': [(6, 0, so_line.tax_id.ids)],
#                     'sale_line_ids': [(6, 0, [so_line.id])],
#                     'analytic_tag_ids': [(6, 0, so_line.analytic_tag_ids.ids)],
#                     'analytic_account_id': order.analytic_account_id.id or False,
#                     'pfb_so_rent_ok': so_line.pfb_so_rent_ok,
#                     'pfb_quantity': so_line.pfb_quantity,
#                     'pfb_insurance_price': so_line.pfb_insurance_price,
#                     'pfb_objective_id': so_line.pfb_objective_id.id,
#                 })],
#             }
#             return invoice_vals
#         else:
#             return super()._prepare_invoice_values(order, name, amount, so_line)




class AccountMove(models.Model):
    _inherit = 'account.move'

    # def _compute_amount_insurance(self):
    #     for order in self:
    #         total = 0.0
    #         for line in order.order_line:
    #             total += (line.pfb_quantity*line.pfb_insurance_price)
    #             print('total',total)
    #
    #         order.pfb_amount_insurance = total
    #         order.pfb_amount = total - order.pfb_dis_amount_insurance

    pfb_so_type = fields.Selection([
        ('sale', 'Sales'),
        ('rent', 'Rent')],
        string="Sale Type",
        index=True, default='sale', required=True)

    pfb_date_of_rent = fields.Integer(string="Day of Rent",)
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")
    pfb_amount_insurance = fields.Float('ค่าประกันสินค้า',digits=0)
    pfb_dis_amount_insurance = fields.Float('ส่วนลดประกันสินค้า',digits=0)
    pfb_amount = fields.Float('ค่าประกันสุทธิ', digits=0)

    # def create(self, values):
    #     print('context--->',self._context)
    #     print('values--->',values)
    #     raise UserError(self.context)
    #     res = super().create(values)
    #     print('res', res)
    #     res.picking_id.write({
    #         'picking_transport_id': res.transport_info_id.id,
    #     })
    #     return res



class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    pfb_so_rent_ok = fields.Boolean('Can be Rent')
    # pfb_date_of_rent = fields.Integer(string="Day of Rent")
    pfb_date_of_rent = fields.Integer(related='sale_line_ids.pfb_date_of_rent')
    pfb_quantity = fields.Integer(string="Quantity Rent")
    pfb_insurance_price = fields.Float(string="Insurance")
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")

