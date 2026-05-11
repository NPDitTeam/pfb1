# Copyright 2009-2018 Noviat
# Copyright 2019 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import calendar
import logging
from odoo import _, api, fields, models
from datetime import datetime
from odoo.exceptions import UserError
from io import BytesIO
import base64

try:
    import qrcode
except ImportError:
    qrcode = None

_logger = logging.getLogger(__name__)

READONLY_STATES = {
    "open": [("readonly", True)],
    "close": [("readonly", True)],
    "removed": [("readonly", True)],
}


class AccountAssetProfile(models.Model):
    _inherit = "account.asset.profile"

    std_asset_sequence_id = fields.Many2one('ir.sequence', string='Entry Sequence')


class AccountAsset(models.Model):
    _inherit = "account.asset"

    std_invoice = fields.Char(string="Invoice No", states=READONLY_STATES)
    std_asset_purchase_id = fields.Many2one('purchase.order', string='Purchase No.', readonly=True)
    std_purchase_price = fields.Float(string="Purchase Price", states=READONLY_STATES)
    std_model = fields.Char(string="Model", states=READONLY_STATES)
    std_purchase_date = fields.Date(string="Purchase Date", states=READONLY_STATES)
    std_serial_no = fields.Char(string="Serial No", states=READONLY_STATES)
    std_employee_id = fields.Many2one('hr.employee', string='Employee', states=READONLY_STATES)
    std_location_id = fields.Many2one('stock.location', string='Location', states=READONLY_STATES)
    std_barcode = fields.Char(string="Asset Number ", states=READONLY_STATES)
    std_condition_type_id = fields.Many2one(
        comodel_name='account.condition.type',
        string='Asset condition',
        required=False,)
    std_condition_remark = fields.Text(string="Remark")
    std_no_compute_asset = fields.Boolean(
        string='No compute Asset',
        required=False)

    def account_asset_sequence(self):
        for asset in self:
            sequence = asset.profile_id.std_asset_sequence_id
            # barcode = self.env["ir.sequence"].next_by_code("account.asset")
            barcode = sequence.with_context(ir_sequence_date=self.date_start).next_by_id()
            asset.std_barcode = barcode
            asset.code = barcode
            if asset.code:
                qr_code = asset.code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_code)
                qr.make(fit=True)

                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                qr_code_image = base64.b64encode(temp.getvalue())

                asset.sh_qr_code_img = qr_code_image
        return True

    @api.model
    def create(self, vals):

        if self.env.context.get("create_asset_from_move_line"):
            vals.update({
                "std_invoice": vals.get('code'),
                "std_purchase_date": vals.get('date_start'),
                "std_purchase_price": vals.get('purchase_value'),
            })
        return super().create(vals)

    def validate(self):
        for asset in self:
            if asset.company_currency_id.is_zero(asset.value_residual) and asset.std_no_compute_asset:
                asset.state = "open"
            elif asset.company_currency_id.is_zero(asset.value_residual):
                asset.state = "close"
            else:
                asset.state = "open"
                if not asset.depreciation_line_ids.filtered(
                        lambda l: l.type != "create"
                ):
                    asset.compute_depreciation_board()
        return True
