# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BranchAddressWizard(models.TransientModel):
    _name = 'branch.address.wizard'
    _description = 'Branch Address Management Wizard'

    branch_id = fields.Many2one(
        'res.branch',
        string='สาขา',
        readonly=True,
    )
    branch_name = fields.Char(
        string='ชื่อสาขา',
        related='branch_id.name',
        readonly=True,
    )
    address_selection = fields.Selection(
        selection='_get_address_selection',
        string='เลือกที่อยู่',
        required=True
    )

    @api.model
    def _get_tax_id(self):
        """ดึงเลขประจำตัวผู้เสียภาษีตาม Database"""
        db_name = self.env.cr.dbname
        tax_id_mapping = {
            'NPD_Intertrading_New': '0105560151261',
            'NPD_Intertrading_New_NonVat': '0105560151261',
            'NPD_Bangkok_New': '0735556006192',
            'NPD_S_Group_New_V2': '0105555146123',
        }
        return tax_id_mapping.get(db_name, '0000000000000')

    @api.model
    def _get_address_selection(self):
        """สร้าง Selection ตาม Database"""
        tax_id = self._get_tax_id()
        return [
            ('address1', '85/13-16 ถนนอรุณอมรินทร์ แขวงอรุณอมรินทร์ เขตบางกอกน้อย กรุงเทพมหานคร 10700'),
            ('address2', '154 ซอยสมเด็จพระปิ่นเกล้า 4 แขวงบางยี่ขัน เขตบางพลัด กรุงเทพมหานคร 10700'),
            ('address3', '85/13-16 ถนนอรุณอมรินทร์ แขวงอรุณอมรินทร์ เขตบางกอกน้อย กรุงเทพมหานคร 10700\nเลขประจำตัวผู้เสียภาษี ' + tax_id),
            ('address4', '154 ซอยสมเด็จพระปิ่นเกล้า 4 แขวงบางยี่ขัน เขตบางพลัด กรุงเทพมหานคร 10700\nเลขประจำตัวผู้เสียภาษี ' + tax_id),
            ('address5', '156  แขวงบางยี่ขัน บางพลัด กรุงเทพมหานคร 10700'),
            ('address6', '156  แขวงบางยี่ขัน บางพลัด กรุงเทพมหานคร 10700\nเลขประจำตัวผู้เสียภาษี ' + tax_id),

        ]

    @api.model
    def _get_address_mapping(self):
        """สร้าง Address Mapping ตาม Database"""
        tax_id = self._get_tax_id()
        return {
            'address1': '85/13-16 ถนนอรุณอมรินทร์ แขวงอรุณอมรินทร์ เขตบางกอกน้อย กรุงเทพมหานคร 10700',
            'address2': '154 ซอยสมเด็จพระปิ่นเกล้า 4 แขวงบางยี่ขัน เขตบางพลัด กรุงเทพมหานคร 10700',
            'address3': '85/13-16 ถนนอรุณอมรินทร์ แขวงอรุณอมรินทร์ เขตบางกอกน้อย กรุงเทพมหานคร 10700\nเลขประจำตัวผู้เสียภาษี ' + tax_id,
            'address4': '154 ซอยสมเด็จพระปิ่นเกล้า 4 แขวงบางยี่ขัน เขตบางพลัด กรุงเทพมหานคร 10700\nเลขประจำตัวผู้เสียภาษี ' + tax_id,
            'address5': '156  แขวงบางยี่ขัน บางพลัด กรุงเทพมหานคร 10700',
            'address6': '156  แขวงบางยี่ขัน บางพลัด กรุงเทพมหานคร 10700\nเลขประจำตัวผู้เสียภาษี ' + tax_id,

        }

    @api.model
    def default_get(self, fields_list):
        res = super(BranchAddressWizard, self).default_get(fields_list)
        # ดึง branch จาก user ที่ login
        user = self.env.user
        if user.branch_id:
            res['branch_id'] = user.branch_id.id
        else:
            raise UserError(_('ไม่พบข้อมูล Branch สำหรับผู้ใช้นี้'))
        return res

    def action_save(self):
        """บันทึกที่อยู่ไปยัง res.branch (ใช้ SQL เพื่อข้ามสิทธิ์ที่ล็อกไม่ให้แก้ไข)"""
        self.ensure_one()

        address_mapping = self._get_address_mapping()
        selected_address = address_mapping.get(self.address_selection, '')

        if self.branch_id and selected_address:
            self.env.cr.execute(
                "UPDATE res_branch SET address = %s, write_date = NOW(), write_uid = %s WHERE id = %s",
                (selected_address, self.env.uid, self.branch_id.id)
            )
            self.env.cr.commit()
            # เคลียร์ cache ของ ORM เพื่อให้อ่านค่าใหม่ได้ถูกต้อง
            self.branch_id.invalidate_cache(['address'], [self.branch_id.id])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('สำเร็จ'),
                'message': _('บันทึกที่อยู่เรียบร้อยแล้ว'),
                'type': 'success',
                'sticky': False,
            }
        }
