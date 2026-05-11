# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, _

class AccountAsset(models.Model):
    _inherit = "account.asset"

    def copy(self, default=None):
        self.ensure_one()
        rec = super().copy(default)
        rec.account_asset_sequence()
        return rec

class AssetDuplicate(models.TransientModel):
    _name = "asset.duplicate"


    number_duplicate = fields.Integer(
        string="Number to Duplicate",
        required=False,
        default=1,
    )

    def action_duplicate(self):
        active_id = self.env.context.get("active_id")
        asset = self.env['account.asset'].browse([active_id])
        number_duplicate = self.number_duplicate
        i = 1
        while i < number_duplicate:
            asset.copy()
            i += 1
        return True