# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models


class ResBank(models.Model):
    _inherit = "res.bank"

    bank_number = fields.Char('No')
    short_name = fields.Char('Short name')
    branch_ref = fields.Char('Branch Ref')
    branch_name = fields.Char('Branch name')