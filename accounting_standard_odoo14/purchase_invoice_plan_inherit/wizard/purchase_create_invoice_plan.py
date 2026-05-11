# Copyright 2019 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import _, api, fields, models


class PurchaseCreateInvoicePlan(models.TransientModel):
    _inherit = "purchase.create.invoice.plan"

    interval_type = fields.Selection(selection_add=[
        ('time', "ครั้ง")], ondelete={'time': 'set default'})
