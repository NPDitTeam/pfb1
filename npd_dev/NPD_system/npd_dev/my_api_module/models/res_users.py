from odoo import models, fields, api
import secrets

class ResUsers(models.Model):
    _inherit = "res.users"

    api_token = fields.Char(string="API Token", copy=False, readonly=True)

    def generate_api_token(self):
        """ สร้าง API Token และบันทึกลงในฟิลด์ """
        for user in self:
            token = secrets.token_hex(32)  # สร้าง Token 32 Bytes
            user.write({'api_token': token})  # บันทึก Token
        return True
