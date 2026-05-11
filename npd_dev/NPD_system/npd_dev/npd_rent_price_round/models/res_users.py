from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    can_edit_use_new_calc = fields.Boolean(
        string='แก้ไข "คิดราคาต่อหน่วยแบบถอด Vat" ได้',
        default=False,
        help='ติ๊กเพื่ออนุญาตให้ผู้ใช้คนนี้สามารถติ๊ก/ยกเลิกฟิลด์ '
             '"คิดราคาต่อหน่วยแบบถอด Vat" และ "ใช้ราคาจากบ้านเขียว" '
             'บน Sale Order และใบแจ้งหนี้/ใบลดหนี้/Debit Note ได้เอง '
             '(ปกติฟิลด์เป็น readonly)',
    )
