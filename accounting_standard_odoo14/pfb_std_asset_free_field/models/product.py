from odoo import api, fields, models
from odoo.tools.float_utils import float_round, float_is_zero


class ProductTemplate(models.Model):
    _inherit = "product.template"

    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        required=False,
    )
