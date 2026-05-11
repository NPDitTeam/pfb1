from odoo import models, fields, api, _


class PurchaseOrderInvoiceInherit(models.Model):
    _inherit = 'purchase.order'

    purchase_type = fields.Selection([
        ('purchase', 'สั่งซื้อ'),
        ('service', 'สั่งจ้าง'),
        ('contract', 'สัญญา'),
    ], default="purchase")

    def action_convert_to_order(self):
        res = super(PurchaseOrderInvoiceInherit, self).action_convert_to_order()
        if self.purchase_order_id:
            if self.purchase_type:
                if self.purchase_type == 'service':
                    self.purchase_order_id.sudo().write(
                        {'name': self.env["ir.sequence"].next_by_code("purchase.sv") or "/", })
                    sequence_id = self.env["ir.sequence"].search([("code", "=", "purchase.order"), ])
                    if sequence_id:
                        sequence_id.number_next_actual = sequence_id.number_next_actual - 1
                if self.purchase_type == 'contract':
                    self.purchase_order_id.sudo().write(
                        {'name': self.env["ir.sequence"].next_by_code("purchase.ct") or "/", })
                    sequence_id = self.env["ir.sequence"].search([("code", "=", "purchase.order"), ])
                    if sequence_id:
                        sequence_id.number_next_actual = sequence_id.number_next_actual - 1
        return res
