# Copyright 2021 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    analytic_account_id = fields.Many2one('account.analytic.account',string='Analytic Account')

    def _prepare_invoice_line(self):
        vals = super()._prepare_invoice_line()
        vals["analytic_account_id"] = self.analytic_account_id
        return vals
