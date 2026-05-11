from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def update_phone_extension(self):
        # ค้นหาเฉพาะ records ที่มีข้อมูลในฟิลด์ phone หรือ mobile และขึ้นต้นด้วย +66
        partners = self.search(['|', ('phone', 'ilike', '+66%'), ('mobile', 'ilike', '+66%')])
        for record in partners:
                # ตรวจสอบว่ามีข้อมูลในฟิลด์ phone หรือ mobile
                phone_number = record.mobile or record.phone
                if phone_number:
                    if phone_number.startswith('+66'):
                        # แปลงหมายเลขโทรศัพท์ที่ขึ้นต้นด้วย +66
                        formatted_number = '0' + phone_number[3:].replace(' ', '')
                    else:
                        # ลบช่องว่างออกจากหมายเลขโทรศัพท์
                        formatted_number = phone_number.replace(' ', '')

                    # อัปเดตฟิลด์ phone และ mobile

                    record.mobile = formatted_number
                    record.phone = formatted_number
