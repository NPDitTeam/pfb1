from odoo import models

class AccountPaymentExtension(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        # ใช้ for loop เพื่อให้ฟังก์ชัน action_post ถูกเรียกทีละ record
        for record in self:
            super(AccountPaymentExtension, record).action_post()
