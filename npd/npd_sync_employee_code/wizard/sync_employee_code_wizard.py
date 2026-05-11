# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class SyncEmployeeCodeWizard(models.TransientModel):
    _name = 'sync.employee.code.wizard'
    _description = 'Wizard อัพเดทรหัสพนักงาน'

    sync_type = fields.Selection(
        [
            ('all', 'อัพเดททั้งหมด'),
            ('branch', 'อัพเดทตามสาขา'),
        ],
        string='ประเภทการอัพเดท',
        default='all',
        required=True,
    )
    branch_id = fields.Many2one(
        'hr.branch.custom',
        string='สาขา',
    )
    # ผลลัพธ์
    result_text = fields.Text(string='ผลการดำเนินการ', readonly=True)
    state = fields.Selection(
        [('config', 'ตั้งค่า'), ('done', 'เสร็จสิ้น')],
        default='config',
    )

    def action_sync(self):
        """
        กดปุ่มอัพเดท - ดำเนินการ sync ตามที่เลือก
        """
        self.ensure_one()
        EmployeeSalary = self.env['employee.salary']

        # กรอง records ตามประเภท
        domain = [('employee_code', '!=', False), ('status', '=', 'active')]
        if self.sync_type == 'branch':
            if not self.branch_id:
                raise UserError('กรุณาเลือกสาขา')
            domain.append(('branch_id', '=', self.branch_id.id))

        records = EmployeeSalary.search(domain)

        if not records:
            self.write({
                'state': 'done',
                'result_text': 'ไม่พบข้อมูลพนักงานที่ต้องอัพเดท',
            })
            return self._reopen_wizard()

        # เรียก batch sync
        results = records.action_sync_employee_code_batch(records)

        # สรุปผล
        summary_lines = [
            '=== สรุปผลการอัพเดทรหัสพนักงาน ===',
            'จำนวนทั้งหมด: %d คน' % len(records),
            'สำเร็จ: %d คน' % results['success_count'],
            'ไม่สำเร็จ: %d คน' % results['failed_count'],
            '',
            '=== รายละเอียด ===',
        ]
        summary_lines.extend(results['messages'])

        self.write({
            'state': 'done',
            'result_text': '\n'.join(summary_lines),
        })

        return self._reopen_wizard()

    def _reopen_wizard(self):
        """
        Reopen wizard เพื่อแสดงผลลัพธ์
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'อัพเดทรหัสพนักงาน',
            'res_model': 'sync.employee.code.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
