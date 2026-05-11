# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from io import BytesIO
import base64
try:
    import qrcode
except ImportError:
    qrcode = None

class AccountAsset(models.Model):
    _inherit = "account.asset"

    sh_qr_code_img = fields.Binary(string="QR Code Image", copy=False)

    @api.onchange('code')
    def onchange_code(self):
        if self:
            if self.code:
                qr_code = self.code
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

                self.sh_qr_code_img = qr_code_image                
                
            else:
                self.code = False
                self.sh_qr_code_img = False    