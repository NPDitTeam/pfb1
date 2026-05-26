from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    bypass_branch_filter = fields.Boolean(
        string='แสดงทุกสาขาในใบแจ้งหนี้',
        help='When checked, this user can see all account moves regardless of branch restrictions'
    )
    bypass_branch_filter_payment = fields.Boolean(
        string='แสดงทุกสาขาในใบรับชำระ',
        help='When checked, this user can see all account payment regardless of branch restrictions'
    )
    sales_view_all_invoice = fields.Boolean(
        string='Sales เห็นใบแจ้งหนี้ทั้งหมด',
        help='สำหรับผู้ใช้แผนก Sales: เมื่อติ๊กถูก จะเห็นใบแจ้งหนี้ทุกสาขาทั้งหมด '
             'แทนที่จะเห็นเฉพาะที่ตัวเองเป็น Sales ที่ติดต่อ (sales_contact_id)'
    )
    sales_view_all_payment = fields.Boolean(
        string='Sales เห็นใบรับชำระทั้งหมด',
        help='สำหรับผู้ใช้แผนก Sales: เมื่อติ๊กถูก จะเห็นใบรับชำระทุกสาขาทั้งหมด '
             'แทนที่จะเห็นเฉพาะที่เกี่ยวข้องกับงานขายของตัวเอง'
    )