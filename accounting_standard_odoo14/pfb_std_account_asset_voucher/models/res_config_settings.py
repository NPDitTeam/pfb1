# Copyright (c) 2014 ACSONE SA/NV (http://acsone.eu).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class Config(models.TransientModel):
    _inherit = 'res.config.settings'

    asset_journal_id = fields.Many2one('account.journal', string='Asset Journal', index=True)
    asset_below_threshold = fields.Float('Asset below the threshold')

    # @api.model
    def get_values(self):
        res = super(Config, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            asset_journal_id=int(
                params.get_param('pfb_std_account_asset_voucher.asset_journal_id', default=False)) or False,
        )
        res.update(
            asset_below_threshold=params.get_param('pfb_std_account_asset_voucher.asset_below_threshold',
                                                   default=False) or False,
        )
        return res

    # @api.multi
    def set_values(self):
        super(Config, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param("pfb_std_account_asset_voucher.asset_journal_id",
                                                         self.asset_journal_id.id or False)
        self.env['ir.config_parameter'].sudo().set_param("pfb_std_account_asset_voucher.asset_below_threshold",
                                                         self.asset_below_threshold or False)
