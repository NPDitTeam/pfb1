from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    central_account_code = fields.Char(
        string='รหัสบัญชีกลาง',
        help='รหัสบัญชีกลาง กรอกได้เฉพาะตัวเลขเท่านั้น',
    )

    @api.constrains('central_account_code')
    def _check_central_account_code(self):
        for record in self:
            code = record.central_account_code
            if code and not code.isdigit():
                raise ValidationError(_(
                    'รหัสบัญชีกลาง "%s" ไม่ถูกต้อง กรุณากรอกเฉพาะตัวเลขเท่านั้น'
                ) % code)
