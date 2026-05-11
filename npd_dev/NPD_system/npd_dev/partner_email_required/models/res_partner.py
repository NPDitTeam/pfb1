# -*- coding: utf-8 -*-
from odoo import api, models, _, tools
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    def _validate_email_mandatory(self):
        """ตรวจว่า partner ทุกตัวต้องมี email และรูปแบบพอใช้ได้"""
        # เปิดทาง bypass แบบเจตนา (เช่น migration) ด้วย context flag
        if self.env.context.get('skip_email_required'):
            return

        for partner in self:
            if not partner.email or not partner.email.strip():
                raise ValidationError(_("กรุณาระบุอีเมล (จำเป็นต้องกรอก)"))
            # ตรวจรูปแบบเบื้องต้นตาม regex เดียวกับ Odoo
            email_re = tools.single_email_re
            if not email_re.match(partner.email.strip()):
                raise ValidationError(_("รูปแบบอีเมลไม่ถูกต้อง: %s") % partner.email)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._validate_email_mandatory()
        return records

    def write(self, vals):
        res = super().write(vals)
        # หลังเขียนเสร็จ ตรวจทุก record ที่เกี่ยวข้อง
        self._validate_email_mandatory()
        return res
