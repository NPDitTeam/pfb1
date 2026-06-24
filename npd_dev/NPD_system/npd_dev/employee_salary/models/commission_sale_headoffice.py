# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class CommissionSaleHeadOffice(models.Model):
    _name = 'commission.sale.headoffice'
    _description = 'จัดการค่าคอม Sales สำนักงานใหญ่'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one(
        'employee.salary',
        string='พนักงาน',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        ('employee_uniq', 'unique(employee_id)',
         'พนักงานคนนี้ถูกเพิ่มในรายชื่อค่าคอม Sales สำนักงานใหญ่แล้ว'),
    ]

    @api.model
    def is_headoffice_employee(self, employee):
        """คืน True ถ้าพนักงานอยู่ในรายชื่อ Sales สำนักงานใหญ่"""
        if not employee:
            return False
        return bool(self.sudo().search_count([('employee_id', '=', employee.id)]))

    def _sync_headoffice_codes(self):
        """sync รายชื่อ (employee_code) ไปยังทุก company DB ทันทีที่เพิ่ม/แก้/ลบ
        → รายงาน ORM + sale.order.copy() ฝั่ง company DB ใช้รายชื่อล่าสุดได้เลย
        ห่อ try/except ไม่ให้ cross-db ที่ล้มเหลวบล็อกการแก้รายชื่อ
        """
        try:
            self.env['cross_db.commission.query'].sudo().push_headoffice_codes()
        except Exception as e:
            _logger.warning("[HEADOFFICE] sync codes ไป company DB ไม่สำเร็จ: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_headoffice_codes()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_headoffice_codes()
        return res

    def unlink(self):
        res = super().unlink()
        # records ถูกลบแล้ว → เรียกผ่าน env model (push อ่านรายชื่อที่เหลือสดใหม่)
        self.env['commission.sale.headoffice']._sync_headoffice_codes()
        return res
