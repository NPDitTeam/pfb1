# Copyright 2009-2018 Noviat
# Copyright 2019 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import calendar
import logging
from odoo import _, api, fields, models
_logger = logging.getLogger(__name__)



class AccountAsset(models.Model):
    _inherit = "account.asset"

    def account_asset_sequence(self):
        for asset in self:
            asset.code = (
                self.env["ir.sequence"].next_by_code("account.asset")
            )
            # asset.write({"code": "billed"})
        return True



