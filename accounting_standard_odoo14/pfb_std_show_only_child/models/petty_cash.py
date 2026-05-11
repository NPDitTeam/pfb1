from odoo import api, fields, models


class PettyExpenseLineTax(models.Model):
    _inherit = "petty.expense.line.tax"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        domain="[('supplier','=',True),('parent_id','=',False)]",
        required=False,
    )