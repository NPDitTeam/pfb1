from odoo import _, api, fields, http, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = "res.company"

    clear_tb_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal Voucher Clear TB",
        required=False,
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    clear_tb_journal_id = fields.Many2one(
        related="company_id.clear_tb_journal_id",
        string='Journal voucher clear tb',
        readonly=False
    )
