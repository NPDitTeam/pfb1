from odoo import api, fields, models


class AdvanceClearLine(models.Model):
    _inherit = "advance.clear.line"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        domain="[('supplier','=',True),('parent_id','=',False)]",
        required=False,
    )


class AccountMoveTaxInvoice(models.Model):
    _inherit = "account.move.tax.invoice"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        domain="[('supplier','=',True),('parent_id','=',False)]",
        required=False,
    )