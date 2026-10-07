from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re  # ใช้สำหรับจัดการรูปแบบข้อความด้วย Regular Expression

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vat = fields.Char(required=True)
    # zip_id = fields.Many2one(
    #     comodel_name="res.city.zip",
    #     string="ZIP Location",
    #     index=True,
    #     compute="_compute_zip_id",
    #     readonly=False,
    #     store=True,
    #     required=True
    # )
    zip_id = fields.Many2one(
        comodel_name="res.city.zip",
        string="ZIP Location",
        index=True,
        compute="_compute_zip_id",
        readonly=False,
        store=True
    )

    phone = fields.Char(required=True, store=True)
    mobile = fields.Char(string="Mobile", store=True)

    @api.constrains('vat')
    def _check_vat_digits(self):
        """
        เลขประจำตัวผู้เสียภาษีต้องเป็นตัวเลขล้วน 13 หลักขึ้นไป
        เช็คเฉพาะรายชื่อหลัก (ผู้ติดต่อย่อยรับค่ามาจากบริษัทแม่ แก้เองไม่ได้)
        ทำงานเฉพาะตอนสร้าง/แก้ช่อง vat — รายชื่อเก่าที่ไม่แตะช่องนี้ไม่โดน
        """
        for rec in self:
            if rec.vat and not rec.parent_id and not re.fullmatch(r'[0-9]{13,}', rec.vat):
                raise ValidationError(_(
                    "เลขประจำตัวผู้เสียภาษีต้องเป็นตัวเลขเท่านั้น และต้องมี 13 หลักขึ้นไป\n"
                    "(ห้ามมีขีด ช่องว่าง หรือตัวอักษร)\n"
                    "หากยังไม่ได้ข้อมูลจากลูกค้าให้ใส่ 0000000000000\n\nที่กรอกมา: %s"
                ) % rec.vat)

    @api.model
    def _strip_vat(self, vals):
        # ตัดช่องว่างหน้า-หลังที่ติดมาตอนก็อปวาง
        if isinstance(vals.get('vat'), str):
            vals['vat'] = vals['vat'].strip()

    def _sanitize_phone_number(self, number):
        """
        ฟังก์ชันสำหรับลบ +66 และเครื่องหมายพิเศษ พร้อมนำเลข 0 มานำหน้า
        และแสดงผลเป็นรูปแบบไม่มีช่องว่าง เช่น 0887729782
        """
        if number:
            # ตัดช่องว่างและเครื่องหมายที่ไม่จำเป็นออก
            number = re.sub(r'\D', '', number)  # ลบตัวอักษรที่ไม่ใช่ตัวเลขทั้งหมด
            if number.startswith('66'):  # หากเริ่มต้นด้วย 66 แทนที่ด้วย 0
                number = '0' + number[2:]
            elif not number.startswith('0'):  # หากไม่มีเลข 0 นำหน้า ให้ใส่ 0
                number = '0' + number
        return number

    @api.model
    def create(self, vals):
        # ทำความสะอาด phone และ mobile ตอนสร้างเรคคอร์ด
        self._strip_vat(vals)
        if 'phone' in vals:
            vals['phone'] = self._sanitize_phone_number(vals['phone'])
        if 'mobile' in vals:
            vals['mobile'] = self._sanitize_phone_number(vals['mobile'])
        return super(ResPartner, self).create(vals)

    def write(self, vals):
        # ทำความสะอาด phone และ mobile ตอนอัปเดตเรคคอร์ด
        self._strip_vat(vals)
        if 'phone' in vals:
            vals['phone'] = self._sanitize_phone_number(vals['phone'])
        if 'mobile' in vals:
            vals['mobile'] = self._sanitize_phone_number(vals['mobile'])
        return super(ResPartner, self).write(vals)
