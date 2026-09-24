from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # เดิมบรรทัดนี้เขียนว่า
    #     partner_id = fields.Many2one('res.partner',
    #                                  compute='onchange_move_type', store=True)
    # ซึ่งทำให้ partner_id กลายเป็นฟิลด์คำนวณที่ "คำนวณแล้วไม่ได้ค่า" เพราะเมธอด
    # ข้างล่างเป็น onchange ที่คืนแค่ domain ไม่เคยกำหนดค่า partner_id เลย
    #
    # ผลคือเวลามีการเขียน invoice_line_ids (แก้จำนวนสินค้าในใบร่างแล้วบันทึก)
    # แกน Odoo เข้าเส้นทาง _move_autocomplete_invoice_lines_write ซึ่งสร้างใบ
    # จำลองในหน่วยความจำแล้วเขียนค่าทั้งชุดกลับลงใบจริง ใบจำลองเรียก compute
    # ตัวนี้แล้วได้ partner_id เป็น False ค่าว่างจึงทับลงใบ ลูกค้าหายทั้งใบ
    #
    # สิ่งที่ผู้เขียนตั้งใจคือ onchange กรองรายชื่อลูกค้าเท่านั้น จึงเอาการนิยาม
    # ฟิลด์ทิ้ง ให้ใช้นิยามเดิมของ account เหลือไว้แค่ onchange ด้านล่าง

    @api.onchange('move_type')
    def onchange_move_type(self):
        if self.move_type == 'out_invoice' or self.move_type == 'out_refund':
            return {'domain': {'partner_id': [('customer', '=', True), ('parent_id', '=', False)]},
                    'string': {'Customer'}
                    }
        else:
            return {'domain': {'partner_id': [('supplier', '=', True), ('parent_id', '=', False)]},
                    'string': {'Vendor'}
                    }

