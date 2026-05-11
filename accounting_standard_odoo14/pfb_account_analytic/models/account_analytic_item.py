# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    account_type_id = fields.Many2one(related='general_account_id.user_type_id',  readonly=True,string='Account Type',store=True)