from odoo import api, fields, models


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = 'account.move'

    def button_reset_tax(self):
        for line in self.line_ids.filtered('tax_line_id'):
            line.with_context(check_move_validity=False).unlink()
        for line in self.invoice_line_ids.filtered('tax_ids'):
            tax_info = line.tax_ids.compute_all(line.price_unit, line.move_id.currency_id, 1, line.product_id, line.move_id.partner_id)
            line.with_context(check_move_validity=False).update({'tax_ids':False,'price_unit':tax_info['total_included']})
        return True
