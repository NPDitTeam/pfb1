from odoo import _, api, fields, models


class PurchaseInvoicePlan(models.Model):
    _inherit = "purchase.invoice.plan"

    plan_date = fields.Date(
        string="Plan Date",
        required=False,
        copy=False
    )

    date_next = fields.Integer(
        string="Day",
    )


