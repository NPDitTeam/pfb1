# -*- coding: utf-8 -*-

from odoo import models, fields, api


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
