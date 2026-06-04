# -*- coding: utf-8 -*-
import calendar
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class WorkSecurityDeposit(models.Model):
    _name = 'work.security.deposit'
    _description = 'เงินประกันการทำงาน'
    _order = 'create_date desc'
    _rec_name = 'name'

    # ตำแหน่งที่ไม่ต้องเก็บเงินประกันการทำงาน (ยกเว้น: ต่างชาติ → เก็บเสมอ ไม่สน position)
    DEPOSIT_EXCLUDED_POSITIONS = (
        'พนง.ซ่อมบำรุง/ยกสินค้า',
        'ไม่ระบุ',
        'พนักงาน ยกสินค้า',
        'พนง.คนงานพม่า/ผลิต',
        'เจ้าหน้าที่ ขนส่ง',
        'เจ้าหน้าที่ ดูแลการส่งเอกสารและซ่อมบำรุง',
        'หน.จนท.กำกับการผลิต/ซ่อมบำรุงสินค้า',
        'จนท.ซบร.ยานพาหนะและทะเบียน',
        'เจ้าหน้าที่ ซ่อมบำรุง',
        'กรรมการ',
        'CEO/ปธ.กรรมการ',
        'COO',
        'จนท.ซ่อมบำรุงยานพาหนะและทะเบียน',
        'จนท.ขส.ประจำสาขา',
    )

    def _filter_eligible_for_deposit(self, employees):
        """กรองพนักงานที่ "ไม่ต้องเก็บเงินประกัน":
        - position อยู่ใน DEPOSIT_EXCLUDED_POSITIONS → ข้าม
        - ยกเว้น: nationality = 'ต่างชาติ' → เก็บเสมอ (ไม่สน position)
        """
        excluded = set(self.DEPOSIT_EXCLUDED_POSITIONS)
        return employees.filtered(lambda e:
            e.nationality == 'ต่างชาติ'
            or (e.position_id.name or 'ไม่ระบุ') not in excluded
        )

    name = fields.Char(string='ชื่อรายการ', compute='_compute_name', store=True)
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา', required=True)
    department_ids = fields.Many2many(
        'hr.department.custom',
        'work_security_deposit_dept_rel', 'deposit_id', 'department_id',
        string='แผนก', required=True,
    )
    available_department_ids = fields.Many2many(
        'hr.department.custom',
        compute='_compute_available_departments',
        string='แผนกที่มีในสาขา',
    )
    cutoff_start_day = fields.Integer(
        string='วันเริ่มรอบ', default=25, required=True,
        help='วันที่เริ่มรอบตัดเงิน (ของเดือนนี้) — ตรงกับรอบของ payroll.period',
    )
    cutoff_end_day = fields.Integer(
        string='วันสิ้นสุดรอบ', default=24, required=True,
        help='วันที่สิ้นสุดรอบตัดเงิน (ของเดือนหน้า) — ใช้กำหนด payment_date ของแต่ละ month_index',
    )
    cutoff_summary = fields.Char(
        string='รอบตัดเงินเดือน', compute='_compute_cutoff_summary',
    )
    default_amount = fields.Float(string='จำนวนเงินที่หัก (บาท)', default=5000.0, required=True)
    default_months = fields.Integer(string='จำนวนเดือนที่หัก', default=3, required=True)
    default_monthly_amount = fields.Float(
        string='เฉลี่ย/เดือน (บาท)', compute='_compute_default_monthly_amount', store=True,
    )
    default_payment_ids = fields.One2many(
        'work.security.deposit.default.payment', 'deposit_id',
        string='หักยอดต่อเดือน (ค่าเริ่มต้น)',
        help='แต่ละแถว = ยอดที่จะหักของเดือนที่ N เริ่มจากวันเริ่มงานของพนักงานแต่ละคน',
    )
    default_total_scheduled = fields.Float(
        string='รวมที่ระบุ (บาท)', compute='_compute_default_total_scheduled', store=True,
    )
    line_ids = fields.One2many('work.security.deposit.line', 'deposit_id', string='รายการพนักงาน')
    state = fields.Selection([
        ('draft', 'ร่าง'),
        ('confirmed', 'ยืนยัน'),
    ], string='สถานะ', default='draft', required=True, readonly=True)
    note = fields.Text(string='หมายเหตุ')

    @api.depends('branch_id', 'department_ids')
    def _compute_name(self):
        for rec in self:
            parts = []
            if rec.branch_id:
                parts.append(rec.branch_id.name)
            if rec.department_ids:
                parts.append('+'.join(rec.department_ids.mapped('name')))
            base = 'เงินประกันการทำงาน - %s' % ' / '.join(parts) if parts else 'เงินประกันการทำงาน'
            rec.name = '%s [#%s]' % (base, rec.id) if isinstance(rec.id, int) else base

    @api.depends('cutoff_start_day', 'cutoff_end_day')
    def _compute_cutoff_summary(self):
        for rec in self:
            rec.cutoff_summary = 'เริ่ม %d เดือนนี้ ถึง %d เดือนหน้า' % (
                rec.cutoff_start_day or 0, rec.cutoff_end_day or 0,
            )

    @api.constrains('cutoff_start_day', 'cutoff_end_day')
    def _check_cutoff_days(self):
        for rec in self:
            if not (1 <= (rec.cutoff_start_day or 0) <= 31):
                raise ValidationError("วันเริ่มรอบต้องอยู่ระหว่าง 1-31")
            if not (1 <= (rec.cutoff_end_day or 0) <= 31):
                raise ValidationError("วันสิ้นสุดรอบต้องอยู่ระหว่าง 1-31")

    @api.constrains('branch_id', 'department_ids')
    def _check_unique_branch_department(self):
        for rec in self:
            if not rec.branch_id or not rec.department_ids:
                continue
            for dept in rec.department_ids:
                duplicate = self.search([
                    ('branch_id', '=', rec.branch_id.id),
                    ('department_ids', 'in', dept.id),
                    ('id', '!=', rec.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        "แผนก '%s' ของสาขา '%s' มีอยู่ใน deposit อื่นแล้ว (ID: %s)" % (
                            dept.name, rec.branch_id.name, duplicate.id,
                        ))

    @api.depends('default_payment_ids.amount', 'default_amount', 'default_months')
    def _compute_default_monthly_amount(self):
        for rec in self:
            n = len(rec.default_payment_ids)
            if n > 0:
                rec.default_monthly_amount = sum(rec.default_payment_ids.mapped('amount')) / n
            elif rec.default_months and rec.default_months > 0:
                rec.default_monthly_amount = rec.default_amount / rec.default_months
            else:
                rec.default_monthly_amount = 0.0

    @api.depends('default_payment_ids.amount')
    def _compute_default_total_scheduled(self):
        for rec in self:
            rec.default_total_scheduled = sum(rec.default_payment_ids.mapped('amount'))

    @api.constrains('default_total_scheduled', 'default_amount')
    def _check_default_total_scheduled(self):
        for rec in self:
            if rec.default_total_scheduled > rec.default_amount + 0.005:
                raise ValidationError(
                    'ผลรวมหักยอดต่อเดือน (%s บาท) เกินจำนวนเงินที่หัก (%s บาท)' % (
                        '{:,.2f}'.format(rec.default_total_scheduled),
                        '{:,.2f}'.format(rec.default_amount),
                    ))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'default_payment_ids' in fields_list and not res.get('default_payment_ids'):
            total = res.get('default_amount', 5000.0)
            months = res.get('default_months', 3)
            res['default_payment_ids'] = self._build_default_payment_commands(total, months)
        return res

    @staticmethod
    def _build_default_payment_commands(total, months):
        """สร้าง command list ของ default_payment_ids แบบเฉลี่ยเท่ากันทุกเดือน
        เดือนสุดท้ายรับเศษเพื่อให้รวมพอดี total"""
        cmds = []
        if not months or months <= 0 or total <= 0:
            return cmds
        monthly = total / months
        remaining = total
        for n in range(1, months + 1):
            if n == months:
                amt = round(remaining, 2)
            else:
                amt = round(monthly, 2)
                remaining -= amt
            cmds.append((0, 0, {'month_index': n, 'amount': amt}))
        return cmds

    @api.onchange('default_months', 'default_amount')
    def _onchange_default_months_amount(self):
        """เมื่อจำนวนเดือนเปลี่ยน: regenerate ทั้งหมด (เฉลี่ยใหม่)
        เมื่อจำนวนเงินเปลี่ยน: regenerate เฉพาะถ้ายังเป็นค่า auto (ผลรวมเดิม = default_amount เดิม) — ไม่งั้นเก็บค่าที่ user แก้ไว้"""
        months = self.default_months or 0
        total = self.default_amount or 0.0
        # Always regenerate when months change. For amount change, only regenerate if user hasn't customized.
        # Simplification: always regenerate (user re-customizes after).
        self.default_payment_ids = [(5, 0, 0)] + self._build_default_payment_commands(total, months)

    @api.depends('branch_id')
    def _compute_available_departments(self):
        Employee = self.env['employee.salary'].sudo()
        for rec in self:
            if rec.branch_id:
                emps = Employee.search([('branch_id', '=', rec.branch_id.id)])
                rec.available_department_ids = emps.mapped('department_id')
            else:
                rec.available_department_ids = self.env['hr.department.custom']

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        self.department_ids = [(5, 0, 0)]
        self.line_ids = [(5, 0, 0)]

    @api.onchange('department_ids')
    def _onchange_department_ids(self):
        """โหลดพนักงานทั้งหมดในแผนก(หลายแผนก) พร้อมสร้างตารางการหักเริ่มต้น"""
        if not self.department_ids or not self.branch_id:
            self.line_ids = [(5, 0, 0)]
            return
        if not self.default_payment_ids and self.default_months and self.default_amount:
            self.default_payment_ids = self._build_default_payment_commands(
                self.default_amount, self.default_months,
            )
        emps = self.env['employee.salary'].sudo().search([
            ('branch_id', '=', self.branch_id.id),
            ('department_id', 'in', self.department_ids.ids),
        ], order='employee_code')
        # ✅ กรองตำแหน่งที่ไม่ต้องเก็บเงินประกัน (ยกเว้นต่างชาติ)
        emps = self._filter_eligible_for_deposit(emps)
        new_lines = [(5, 0, 0)]
        defaults = sorted(
            [(p.month_index, p.amount) for p in self.default_payment_ids],
            key=lambda x: x[0],
        )
        total = self.default_amount or 0.0
        cutoff_start = self.cutoff_start_day or 25
        cutoff_end = self.cutoff_end_day or 24
        for emp in emps:
            start = emp.start_date or fields.Date.context_today(self)
            payment_cmds = self._build_line_payments_from_defaults(
                start, defaults, cutoff_start, cutoff_end,
            )
            line_vals = {
                'employee_id': emp.id,
                'start_work_date': start,
                'total_amount': total,
                'work_status': 'working',
                'payment_ids': payment_cmds,
            }
            # Auto-check Work Permit ถ้าพนักงานสัญชาติต่างชาติ
            if emp.nationality == 'ต่างชาติ':
                regular_dates = [d for (d, _v) in [
                    (cmd[2]['payment_date'], cmd[2]['amount']) for cmd in payment_cmds
                ]]
                line_vals['is_work_permit'] = True
                line_vals['work_permit_payment_ids'] = self._build_work_permit_default_payments(
                    start, regular_dates,
                )
            new_lines.append((0, 0, line_vals))
        self.line_ids = new_lines

    @staticmethod
    def _build_work_permit_default_payments(start_date, regular_dates=None):
        """สร้าง command list ของ work_permit default 3 ประเภท
        ใช้ regular_dates เป็น payment_date ถ้ามี ไม่งั้น fallback start_date (วันที่ 1 ของเดือน)"""
        defaults_types = ['work_permit_fee', 'visa_fee', 'document_service']
        if not start_date:
            return []
        regular_dates = regular_dates or []
        fallback = start_date.replace(day=1)
        cmds = []
        for idx, ptype in enumerate(defaults_types):
            if idx < len(regular_dates):
                d = regular_dates[idx]
            elif regular_dates:
                d = regular_dates[-1]
            else:
                d = fallback
            cmds.append((0, 0, {
                'payment_type': ptype,
                'payment_date': d,
                'amount': 0.0,
            }))
        return cmds

    @staticmethod
    def _build_line_payments_from_defaults(start_date, defaults, cutoff_start=25, cutoff_end=24):
        """แปลง list ของ (month_index, amount) เป็น payment_ids commands

        Cycle N: เริ่มวันที่ cutoff_start ของเดือน X+(N-1), จบวันที่ cutoff_end ของเดือน X+N
        payment_date ของ Cycle N = วัน cutoff_end ของเดือน X+N
          (X = เดือนแรกที่ครอบคลุม start_date เต็มรอบ)

        ถ้า start_date.day > cutoff_start → cycle 1 เริ่มเดือนถัดไป (เก็บไม่ทันรอบนี้)
        ถ้า start_date.day <= cutoff_start → cycle 1 เริ่มเดือนนี้
        """
        import calendar
        cmds = []
        if not start_date or not defaults:
            return cmds
        # หาเดือนเริ่มต้นของ cycle 1
        if start_date.day > cutoff_start:
            base_month_offset = 1
        else:
            base_month_offset = 0
        for month_idx, amt in defaults:
            if amt <= 0:
                continue
            # cycle N starts at month X+(N-1), ends at month X+N
            cycle_end_offset = base_month_offset + month_idx
            cycle_end_date = start_date + relativedelta(months=cycle_end_offset)
            # ใช้วัน cutoff_end (clamp ตามจำนวนวันในเดือน)
            last_day = calendar.monthrange(cycle_end_date.year, cycle_end_date.month)[1]
            day = min(cutoff_end, last_day)
            d = cycle_end_date.replace(day=day)
            cmds.append((0, 0, {'payment_date': d, 'amount': amt}))
        return cmds

    @api.model_create_multi
    def create(self, vals_list):
        deposits = super().create(vals_list)
        for d in deposits:
            d._fill_missing_line_payments()
        return deposits

    def _fill_missing_line_payments(self):
        """หลัง save: ถ้า line ไหน payment_ids ว่าง → สร้างจาก default_payment_ids ของ deposit"""
        for d in self:
            if not d.default_payment_ids:
                continue
            defaults = sorted(
                [(p.month_index, p.amount) for p in d.default_payment_ids],
                key=lambda x: x[0],
            )
            for line in d.line_ids:
                if line.payment_ids or line.skip_deduction:
                    continue
                cmds = self._build_line_payments_from_defaults(
                    line.start_work_date, defaults,
                    d.cutoff_start_day or 25, d.cutoff_end_day or 24,
                )
                if cmds:
                    line.payment_ids = cmds

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError("กรุณาเลือกแผนกเพื่อโหลดรายชื่อพนักงานก่อน")
            if rec.default_total_scheduled > rec.default_amount + 0.005:
                raise UserError(
                    "ผลรวมหักยอดต่อเดือน (%s บาท) เกินจำนวนเงินที่หัก (%s บาท)\n"
                    "กรุณาแก้ไขให้ผลรวมไม่เกินจำนวนเงินที่หัก" % (
                        '{:,.2f}'.format(rec.default_total_scheduled),
                        '{:,.2f}'.format(rec.default_amount),
                    ))
            rec._fill_missing_line_payments()
            rec.state = 'confirmed'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_mark_historical_old_employees(self):
        """ทำเครื่องหมายเศษย้อนหลัง: วน lines ที่ payment_dates ทั้งหมดอยู่ในอดีต
        → ตั้ง is_synced=True ทุก payment เพื่อแสดงว่าหักครบไปแล้ว (ก่อนใช้ระบบ)"""
        self.ensure_one()
        today = fields.Date.context_today(self)
        marked_lines = self.env['work.security.deposit.line']
        marked_payments_count = 0
        for line in self.line_ids:
            if line.work_status != 'working':
                continue
            past_payments = line.payment_ids.filtered(
                lambda p: p.payment_date and p.payment_date <= today and not p.is_synced
            )
            if not past_payments:
                continue
            # เช็คว่า payment ทุกตัวของ line อยู่ในอดีต (เป็นพนักงานเก่าจริงๆ)
            all_past = all(
                p.payment_date and p.payment_date <= today
                for p in line.payment_ids
            )
            if not all_past:
                continue
            past_payments.write({'is_synced': True})
            marked_lines |= line
            marked_payments_count += len(past_payments)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ทำเครื่องหมายเศษย้อนหลัง',
                'message': 'ตั้ง %d รายการ เป็น "หักแล้ว" สำหรับพนักงาน %d คน' % (
                    marked_payments_count, len(marked_lines),
                ),
                'type': 'success' if marked_lines else 'info',
                'sticky': False,
            }
        }

    def action_regenerate_all_schedules(self):
        """ปรับ payment_ids ของทุก line ให้ตรงกับ default_payment_ids ปัจจุบัน
        (สำหรับเคสที่แก้ค่า default หลังจากสร้าง lines ไปแล้ว)
        Preserve: จำนวน is_synced ของ regular payments เดิม → mark N รายการแรกที่สร้างใหม่"""
        self.ensure_one()
        if not self.default_payment_ids:
            raise UserError("กรุณาตั้งค่า 'หักรายเดือน (ค่าเริ่มต้น)' ก่อน")
        defaults = sorted(
            [(p.month_index, p.amount) for p in self.default_payment_ids],
            key=lambda x: x[0],
        )
        cutoff_start = self.cutoff_start_day or 25
        cutoff_end = self.cutoff_end_day or 24
        updated_count = 0
        for line in self.line_ids:
            if line.work_status != 'working':
                continue
            # Sync start_work_date จาก employee.salary.start_date ปัจจุบัน
            # (กรณี user แก้ employee.start_date หลังจากสร้าง line ไปแล้ว)
            emp_start = line.employee_id.start_date if line.employee_id else False
            if emp_start and line.start_work_date != emp_start:
                line.start_work_date = emp_start
            # นับ regular payment ที่เคย synced ไว้ — preserve ตอน regenerate
            old_regular_synced = line.payment_ids.filtered(
                lambda p: p.payment_type == 'regular' and p.is_synced
            )
            old_synced_count = len(old_regular_synced)
            # เก็บ payroll_id ตามลำดับเดือนเดิม เพื่อ map กลับ
            old_payroll_ids = old_regular_synced.sorted('payment_date').mapped('payroll_id')
            cmds = self._build_line_payments_from_defaults(
                line.start_work_date, defaults, cutoff_start, cutoff_end,
            )
            if not cmds:
                continue
            line.payment_ids.filtered(lambda p: p.payment_type == 'regular').unlink()
            line.write({
                'total_amount': self.default_amount,
                'payment_ids': cmds,
            })
            new_regular = line.payment_ids.filtered(
                lambda p: p.payment_type == 'regular'
            ).sorted('payment_date')
            # Re-apply is_synced + payroll_id ของรอบที่เคย sync แล้ว
            if old_synced_count:
                for idx, new_p in enumerate(new_regular[:old_synced_count]):
                    vals = {'is_synced': True}
                    if idx < len(old_payroll_ids) and old_payroll_ids[idx]:
                        vals['payroll_id'] = old_payroll_ids[idx].id
                    new_p.write(vals)
            else:
                # ถ้าไม่มี synced เดิม + payment_dates ทุกอันอยู่ในอดีต → mark historical
                today = fields.Date.context_today(self)
                if new_regular and all(
                    p.payment_date and p.payment_date <= today for p in new_regular
                ):
                    new_regular.write({'is_synced': True})
            updated_count += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ปรับตารางทั้งหมด',
                'message': 'อัพเดทตารางของ %d พนักงาน ตามค่าเริ่มต้นปัจจุบัน' % updated_count,
                'type': 'success' if updated_count else 'info',
                'sticky': False,
            }
        }

    def action_sync_resign_dates(self):
        """ดึง resign_date จาก employee.salary ของแต่ละ line มาเซ็ตในตาราง
        + ตั้ง work_status = 'resigned' ให้อัตโนมัติ
        ใช้เมื่อมีการอัพเดท resign_date ที่ employee.salary แล้ว
        และต้องการให้ deposit รับรู้ + คำนวณ refund"""
        self.ensure_one()
        updated = 0
        for line in self.line_ids:
            emp = line.employee_id
            if not emp:
                continue
            emp_resign = getattr(emp, 'resign_date', False)
            if not emp_resign:
                continue
            # เทียบกับค่าใน line — อัพเดทเฉพาะที่เปลี่ยน
            if line.resign_date != emp_resign or line.work_status != 'resigned':
                line.write({
                    'resign_date': emp_resign,
                    'work_status': 'resigned',
                })
                updated += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ดึงวันที่ออกจากงาน',
                'message': 'อัพเดท %d รายการ' % updated,
                'type': 'success' if updated > 0 else 'warning',
                'sticky': False,
            }
        }

    def _get_candidate_employees(self):
        """พนักงานใหม่ในสาขา+แผนกเดียวกัน ที่ยังไม่อยู่ใน line_ids (กรองตำแหน่งที่ไม่เก็บประกัน)"""
        self.ensure_one()
        existing_emp_ids = self.line_ids.mapped('employee_id').ids
        new_emps = self.env['employee.salary'].sudo().search([
            ('branch_id', '=', self.branch_id.id),
            ('department_id', 'in', self.department_ids.ids),
            ('id', 'not in', existing_emp_ids),
        ], order='employee_code')
        return self._filter_eligible_for_deposit(new_emps)

    def _add_employees_to_deposit(self, employees):
        """เพิ่มพนักงานที่เลือกเข้า line_ids พร้อม schedule เริ่มต้น — คืนจำนวนที่เพิ่ม"""
        self.ensure_one()
        if not employees:
            return 0
        defaults = sorted(
            [(p.month_index, p.amount) for p in self.default_payment_ids],
            key=lambda x: x[0],
        )
        if not defaults and self.default_months and self.default_amount:
            self.default_payment_ids = self._build_default_payment_commands(
                self.default_amount, self.default_months,
            )
            defaults = sorted(
                [(p.month_index, p.amount) for p in self.default_payment_ids],
                key=lambda x: x[0],
            )
        cutoff_start = self.cutoff_start_day or 25
        cutoff_end = self.cutoff_end_day or 24
        # กันซ้ำ — ตัดคนที่อยู่ใน line_ids แล้วออก
        existing_emp_ids = set(self.line_ids.mapped('employee_id').ids)
        new_line_cmds = []
        for emp in employees:
            if emp.id in existing_emp_ids:
                continue
            start = emp.start_date or fields.Date.context_today(self)
            payment_cmds = self._build_line_payments_from_defaults(
                start, defaults, cutoff_start, cutoff_end,
            )
            line_vals = {
                'employee_id': emp.id,
                'start_work_date': start,
                'total_amount': self.default_amount,
                'work_status': 'working',
                'payment_ids': payment_cmds,
            }
            if emp.nationality == 'ต่างชาติ':
                regular_dates = [cmd[2]['payment_date'] for cmd in payment_cmds]
                line_vals['is_work_permit'] = True
                line_vals['work_permit_payment_ids'] = self._build_work_permit_default_payments(
                    start, regular_dates,
                )
            new_line_cmds.append((0, 0, line_vals))
        if new_line_cmds:
            self.sudo().write({'line_ids': new_line_cmds})
        return len(new_line_cmds)

    def action_refresh_employees(self):
        """ดึงพนักงานใหม่ → เปิด popup ให้เลือกว่าจะเพิ่มใครเข้าทำเงินประกัน"""
        self.ensure_one()
        if not self.branch_id or not self.department_ids:
            raise UserError("กรุณาเลือกสาขาและแผนกก่อน")
        candidates = self._get_candidate_employees()
        if not candidates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'ดึงข้อมูลพนักงาน',
                    'message': 'ไม่พบพนักงานใหม่ในสาขา/แผนกนี้ — รายชื่อในตารางเป็นปัจจุบันแล้ว',
                    'type': 'info',
                    'sticky': False,
                }
            }
        wizard = self.env['work.security.deposit.add.wizard'].create({
            'deposit_id': self.id,
            'candidate_employee_ids': [(6, 0, candidates.ids)],
            'employee_ids': [(6, 0, candidates.ids)],  # เลือกไว้ทั้งหมดก่อน — ติ๊กออกได้
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'เลือกพนักงานที่จะเพิ่ม',
            'res_model': 'work.security.deposit.add.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_sync_to_payroll(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError("กรุณายืนยันรายการก่อนซิงค์ไป payroll")
        updated = 0
        for line in self.line_ids:
            updated += line._sync_to_payroll()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ซิงค์ไป Payroll',
                'message': 'อัพเดท payroll.salary จำนวน %d รายการ' % updated,
                'type': 'success' if updated else 'warning',
                'sticky': False,
            }
        }


class WorkSecurityDepositLine(models.Model):
    _name = 'work.security.deposit.line'
    _description = 'รายละเอียดเงินประกันการทำงาน (รายคน)'
    _rec_name = 'employee_id'

    deposit_id = fields.Many2one('work.security.deposit', string='รายการ',
                                 required=True, ondelete='cascade')
    state = fields.Selection(related='deposit_id.state', store=True, readonly=True)

    employee_id = fields.Many2one('employee.salary', string='พนักงาน', required=True)
    employee_code = fields.Char(related='employee_id.employee_code', string='รหัส', store=True, readonly=True)
    firstname = fields.Char(related='employee_id.firstname', string='ชื่อ', store=True, readonly=True)
    lastname = fields.Char(related='employee_id.lastname', string='นามสกุล', store=True, readonly=True)
    employee_status = fields.Selection(
        related='employee_id.status', string='สถานะการใช้งาน', store=True, readonly=True,
    )
    employee_department_id = fields.Many2one(
        'hr.department.custom', related='employee_id.department_id',
        string='แผนก', store=True, readonly=True,
    )
    employee_branch_id = fields.Many2one(
        'hr.branch.custom', related='employee_id.branch_id',
        string='สาขาปัจจุบัน', store=True, readonly=True,
    )
    employee_nationality = fields.Selection(
        related='employee_id.nationality', string='สัญชาติ', store=True, readonly=True,
    )

    start_work_date = fields.Date(string='วันที่เริ่มงาน', required=True)
    total_amount = fields.Float(string='จำนวนเงินที่หัก (บาท)', default=5000.0, required=True,
                                help='จำนวนเงินรวมสูงสุดที่จะหัก ผลรวมของตารางหักรายเดือนต้องไม่เกินค่านี้')
    skip_deduction = fields.Boolean(
        string='ไม่หักเงินประกัน (คนนี้)', default=False,
        help='ติ๊กเพื่อไม่หักเงินประกันสำหรับพนักงานคนนี้ — ระบบจะไม่สร้าง/เติมตารางหักรายเดือนให้ '
             'และตอนกดยืนยัน deposit จะไม่เด้งตารางกลับมา (กันภาระคืนเงินตอนลาออก)')

    payment_ids = fields.One2many(
        'work.security.deposit.line.payment', 'line_id',
        string='ตารางหักรายเดือน',
        domain=[('payment_type', '=', 'regular')],
        help='ระบุเดือน + จำนวนเงินที่จะหักของแต่ละเดือน',
    )
    is_work_permit = fields.Boolean(
        string='Work Permit', default=False,
        help='สำหรับพนักงานต่างชาติ — ติ๊กเพื่อเปิดตารางหักค่าธรรมเนียมใบอนุญาตทำงาน, '
             'วีซ่า, ค่าบริการทำเอกสาร (หักรวมกับเงินประกันการทำงาน, ไม่คืนเงิน)',
    )
    work_permit_payment_ids = fields.One2many(
        'work.security.deposit.line.payment', 'line_id',
        string='ตารางหัก Work Permit',
        domain=[('payment_type', '!=', 'regular')],
    )
    work_permit_total = fields.Float(
        string='รวมค่า Work Permit (บาท)',
        compute='_compute_work_permit_total', store=True,
    )
    total_scheduled = fields.Float(
        string='รวมที่หักจริง (บาท)', compute='_compute_totals', store=True,
    )
    deduction_months = fields.Integer(
        string='จำนวนเดือนที่หัก', compute='_compute_totals', store=True,
    )
    monthly_amount = fields.Float(
        string='เฉลี่ย/เดือน (บาท)', compute='_compute_totals', store=True,
    )
    last_deduction_date = fields.Date(
        string='เดือนสุดท้ายที่หัก', compute='_compute_totals', store=True,
    )
    schedule_summary = fields.Char(string='สรุป', compute='_compute_schedule_summary')

    work_status = fields.Selection([
        ('working', 'ทำงานอยู่'),
        ('resigned', 'ออกจากงาน'),
        ('transferred', 'ย้ายแผนก/สาขา'),
    ], string='สถานะการทำงาน', default='working', required=True)
    resign_date = fields.Date(string='วันที่ออกจากงาน')
    transferred_date = fields.Date(string='วันที่ย้าย')
    transferred_to_line_id = fields.Many2one(
        'work.security.deposit.line', string='ย้ายไป (line ใหม่)', readonly=True,
        ondelete='set null',
    )
    transferred_from_line_id = fields.Many2one(
        'work.security.deposit.line', string='ย้ายมาจาก (line เก่า)', readonly=True,
        ondelete='set null',
    )

    months_deducted = fields.Integer(
        string='เดือนที่หักไปแล้ว',
        compute='_compute_resign_info',
        inverse='_inverse_months_deducted',
        store=True,
        readonly=False,
    )
    refund_amount = fields.Float(
        string='เงินที่ต้องคืน (บาท)',
        compute='_compute_resign_info',
        inverse='_inverse_refund_amount',
        store=True,
        readonly=False,
    )
    refund_payroll_id = fields.Many2one(
        'payroll.salary', string='Payroll ที่คืนเงิน', readonly=True, ondelete='set null',
        help='Payroll record ที่ประมวลผลการคืนเงินประกัน (เดือนที่ออกจากงาน)',
    )
    refund_status = fields.Selection([
        ('none', 'ไม่ต้องคืน'),
        ('pending', 'รอคืนเงิน'),
        ('refunded', 'คืนแล้ว'),
    ], string='สถานะการคืนเงิน', compute='_compute_refund_status', store=True)
    manual_refunded = fields.Boolean(
        string='ปรับสถานะ "คืนแล้ว" เอง', default=False,
        help='ติ๊กเพื่อบังคับให้ refund_status = "คืนแล้ว" — ใช้กับเศษพนักงานเก่าที่ไม่ผ่านระบบทำเงินเดือน',
    )
    manual_refunded_date = fields.Date(string='วันที่คืน (ระบุเอง)')
    manual_refunded_note = fields.Char(string='หมายเหตุการคืน (ระบุเอง)')

    @api.depends('payment_ids', 'payment_ids.amount', 'payment_ids.payment_date',
                 'payment_ids.payment_type')
    def _compute_totals(self):
        for rec in self:
            regular = rec.payment_ids.filtered(
                lambda p: p.payment_type == 'regular'
            ).sorted('payment_date')
            rec.total_scheduled = sum(regular.mapped('amount'))
            rec.deduction_months = len(regular)
            rec.monthly_amount = (rec.total_scheduled / rec.deduction_months) if rec.deduction_months else 0.0
            rec.last_deduction_date = regular[-1].payment_date if regular else False

    @api.depends('work_permit_payment_ids.amount')
    def _compute_work_permit_total(self):
        for rec in self:
            rec.work_permit_total = sum(rec.work_permit_payment_ids.mapped('amount'))

    @api.onchange('is_work_permit')
    def _onchange_is_work_permit(self):
        """ติ๊ก Work Permit → auto-add 3 row default (1 ต่อประเภท)
        payment_date เริ่มต้นใช้เดือนเดียวกับ payment_ids ของ regular ถ้ามี"""
        if not self.is_work_permit:
            return
        existing_types = set(self.work_permit_payment_ids.mapped('payment_type'))
        defaults = ['work_permit_fee', 'visa_fee', 'document_service']
        # ดึงวันที่จาก payment_ids ของ regular มาใช้เป็นค่าเริ่มต้น (1:1 mapping)
        regular_dates = [
            p.payment_date for p in self.payment_ids.sorted('payment_date')
            if p.payment_date
        ]
        fallback_date = (self.start_work_date or fields.Date.context_today(self)).replace(day=1)
        new_rows = []
        for idx, ptype in enumerate(defaults):
            if ptype in existing_types:
                continue
            if idx < len(regular_dates):
                d = regular_dates[idx]
            elif regular_dates:
                d = regular_dates[-1]
            else:
                d = fallback_date
            new_rows.append((0, 0, {
                'payment_type': ptype,
                'payment_date': d,
                'amount': 0.0,
            }))
        if new_rows:
            self.work_permit_payment_ids = new_rows

    @api.depends('payment_ids.amount', 'total_amount', 'total_scheduled', 'deduction_months')
    def _compute_schedule_summary(self):
        for rec in self:
            if rec.deduction_months:
                rec.schedule_summary = '%s บาท / %d เดือน' % (
                    '{:,.2f}'.format(rec.total_scheduled), rec.deduction_months,
                )
            else:
                rec.schedule_summary = ''

    @api.depends('payment_ids.amount', 'payment_ids.is_synced', 'payment_ids.payment_type')
    def _compute_resign_info(self):
        """นับเฉพาะ payment_type='regular' ที่ is_synced สำหรับ refund
        (work_permit ไม่คืนเงิน)"""
        for rec in self:
            paid = rec.payment_ids.filtered(
                lambda p: p.is_synced and p.payment_type == 'regular'
            )
            rec.months_deducted = len(paid)
            rec.refund_amount = sum(paid.mapped('amount'))

    @api.depends('work_status', 'refund_payroll_id', 'refund_amount', 'manual_refunded')
    def _compute_refund_status(self):
        for rec in self:
            if rec.manual_refunded:
                rec.refund_status = 'refunded'
            elif rec.work_status != 'resigned' or rec.refund_amount <= 0:
                rec.refund_status = 'none'
            elif rec.refund_payroll_id:
                rec.refund_status = 'refunded'
            else:
                rec.refund_status = 'pending'

    def action_mark_refunded_manual(self):
        """ปรับสถานะ 'คืนแล้ว' โดยไม่ผ่าน payroll — สำหรับเศษพนักงานเก่า"""
        for rec in self:
            rec.write({
                'manual_refunded': True,
                'manual_refunded_date': rec.manual_refunded_date or fields.Date.context_today(rec),
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ปรับสถานะคืนแล้ว',
                'message': 'ปรับ %d รายการ เป็น "คืนแล้ว"' % len(self),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_unmark_refunded_manual(self):
        """ยกเลิกการ mark คืนเงินแบบ manual"""
        for rec in self:
            rec.write({
                'manual_refunded': False,
                'manual_refunded_date': False,
                'manual_refunded_note': False,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ยกเลิกสถานะคืนแล้ว',
                'message': 'ยกเลิก %d รายการ' % len(self),
                'type': 'success',
                'sticky': False,
            }
        }

    def _inverse_months_deducted(self):
        # User override — ค่าที่ user แก้จะถูกเก็บไว้
        return

    def _inverse_refund_amount(self):
        return

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if not self.employee_id:
            return
        if not self.start_work_date:
            self.start_work_date = self.employee_id.start_date
        # auto-fill ข้อมูลออกจากงาน จาก employee.salary
        if self.employee_id.resign_date:
            self.resign_date = self.employee_id.resign_date
            self.work_status = 'resigned'
        # Auto-check Work Permit ถ้าพนักงานสัญชาติต่างชาติ
        if self.employee_id.nationality == 'ต่างชาติ' and not self.is_work_permit:
            self.is_work_permit = True
            self._onchange_is_work_permit()

    @api.onchange('work_status')
    def _onchange_work_status(self):
        if self.work_status == 'resigned' and not self.resign_date:
            self.resign_date = fields.Date.context_today(self)
        elif self.work_status == 'working':
            self.resign_date = False

    @api.model_create_multi
    def create(self, vals_list):
        """หลังสร้าง line ถ้า payment_ids ว่าง — auto-fill จาก default_payment_ids ของ deposit"""
        records = super().create(vals_list)
        for rec in records:
            if rec.payment_ids or rec.skip_deduction:
                continue
            d = rec.deposit_id
            if not d or not d.default_payment_ids:
                continue
            defaults = sorted(
                [(p.month_index, p.amount) for p in d.default_payment_ids],
                key=lambda x: x[0],
            )
            cmds = WorkSecurityDeposit._build_line_payments_from_defaults(
                rec.start_work_date, defaults,
                d.cutoff_start_day or 25, d.cutoff_end_day or 24,
            )
            if cmds:
                rec.payment_ids = cmds
        return records

    @api.constrains('total_scheduled', 'total_amount')
    def _check_total_scheduled(self):
        for rec in self:
            if rec.total_scheduled > rec.total_amount + 0.005:
                raise ValidationError(
                    "ผลรวมของตารางหักรายเดือนของ %s (%s บาท) "
                    "เกินจำนวนเงินที่หัก (%s บาท)" % (
                        rec.employee_id.firstname or '',
                        '{:,.2f}'.format(rec.total_scheduled),
                        '{:,.2f}'.format(rec.total_amount),
                    ))

    @api.constrains('work_status', 'resign_date')
    def _check_resign_date(self):
        for rec in self:
            if rec.work_status == 'resigned' and not rec.resign_date:
                raise ValidationError("กรุณาระบุวันที่ออกจากงานสำหรับพนักงานที่ออกจากงาน")

    @api.constrains('deposit_id', 'employee_id', 'work_status')
    def _check_unique_active_employee(self):
        for rec in self:
            if rec.work_status != 'working':
                continue
            if not rec.deposit_id or not rec.employee_id:
                continue
            duplicate = self.search([
                ('deposit_id', '=', rec.deposit_id.id),
                ('employee_id', '=', rec.employee_id.id),
                ('work_status', '=', 'working'),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "พนักงาน %s (%s) มีอยู่ใน deposit นี้แล้ว (สถานะ: ทำงานอยู่)\n"
                    "ห้ามมี active line ซ้ำสำหรับพนักงานเดียวกัน" % (
                        rec.employee_id.firstname or '',
                        rec.employee_id.employee_code or '',
                    ))

    # ============================================================
    # Action: regenerate ตารางการหักเริ่มต้น (จาก deposit defaults)
    # ============================================================
    def action_regenerate_schedule(self):
        """ลบตารางเดิมแล้วสร้างใหม่จาก default_payment_ids ของ deposit"""
        for rec in self:
            d = rec.deposit_id
            defaults = sorted(
                [(p.month_index, p.amount) for p in d.default_payment_ids],
                key=lambda x: x[0],
            )
            cmds = WorkSecurityDeposit._build_line_payments_from_defaults(
                rec.start_work_date, defaults,
                d.cutoff_start_day or 25, d.cutoff_end_day or 24,
            )
            rec.payment_ids.unlink()
            rec.write({
                'total_amount': d.default_amount,
                'payment_ids': cmds,
                'skip_deduction': False,  # สร้างตารางใหม่ = กลับมาหักปกติ
            })
        return True

    def action_clear_regular_schedule(self):
        """ลบตารางหักรายเดือน (regular) ที่ "ยังไม่ส่งเข้า payroll" ของพนักงานคนนี้ทั้งหมด
        ใช้กรณีพนักงานที่ไม่ต้องหักเงินประกัน → จะได้ไม่มีภาระคืนเงินตอนลาออก

        ทำฝั่ง server โดยตรง เพราะในฟอร์มมี One2many 2 ตัวบน inverse เดียวกัน
        (payment_ids + work_permit_payment_ids) ทำให้ลบทีละแถวแล้วเซฟไม่ติด
        — รายการที่หักแล้ว (is_synced) จะไม่ถูกลบ เพื่อกันลบยอดที่หักจริงไปแล้ว"""
        for rec in self:
            to_del = rec.payment_ids.filtered(
                lambda p: p.payment_type == 'regular' and not p.is_synced)
            if to_del:
                to_del.unlink()
            # ติ๊ก skip ให้ → กันตอนกดยืนยัน/สร้าง deposit เด้งตารางกลับมา
            rec.skip_deduction = True
        return True

    # ============================================================
    # Sync to payroll
    # ============================================================
    def _sync_to_payroll(self):
        """ผลักจำนวนรายเดือนตามตารางการหักเข้า payroll.salary.expense_insurance
        + กรณี resigned: refresh payroll ของเดือน resign เพื่อ trigger refund + ตั้ง refund_payroll_id"""
        self.ensure_one()
        if not self.employee_id:
            return 0
        Period = self.env['payroll.period'].sudo()
        Payroll = self.env['payroll.salary'].sudo()
        updated = 0
        for payment in self.payment_ids.sorted('payment_date'):
            d = payment.payment_date
            if not d or payment.amount <= 0:
                continue
            if self.work_status == 'resigned' and self.resign_date and d > self.resign_date:
                continue
            period = Period.search([
                ('month', '=', d.month),
                ('year', '=', str(d.year)),
            ], limit=1)
            if not period:
                continue
            payroll = Payroll.search([
                ('employee_id', '=', self.employee_id.id),
                ('period_id', '=', period.id),
            ], limit=1)
            if not payroll:
                continue
            payroll.write({'expense_insurance': payment.amount})
            try:
                payroll._populate_all_lines()
            except Exception as e:
                _logger.warning("Could not refresh payroll lines for %s: %s",
                                self.employee_id.employee_code, e)
            payment.write({'is_synced': True, 'payroll_id': payroll.id})
            updated += 1
        # ถ้า resigned → refresh payroll ของเดือน resign เพื่อ trigger refund + refund_payroll_id
        if self.work_status == 'resigned' and self.resign_date:
            rd = self.resign_date
            resign_payroll = Payroll.search([
                ('employee_id', '=', self.employee_id.id),
                ('month', '=', rd.month),
                ('year', '=', str(rd.year)),
            ], limit=1)
            if resign_payroll:
                resign_payroll._refresh_security_deposit()
                updated += 1
        return updated

    @api.model
    def _get_amount_for_payroll(self, employee_id, year, month):
        """หาจำนวนที่ต้องหักของพนักงานในเดือน/ปีนั้น โดยอ่านจาก payment_ids ของ deposit ที่ confirmed
        skip lines ที่ resigned หลัง resign_date และ skip transferred หลัง transferred_date"""
        Payment = self.env['work.security.deposit.line.payment'].sudo()
        payments = Payment.search([
            ('line_id.employee_id', '=', employee_id),
            ('line_id.deposit_id.state', '=', 'confirmed'),
        ])
        total = 0.0
        for p in payments:
            line = p.line_id
            if line.work_status == 'resigned' and line.resign_date and p.payment_date and p.payment_date > line.resign_date:
                continue
            if line.work_status == 'transferred' and line.transferred_date and p.payment_date and p.payment_date > line.transferred_date:
                continue
            if p.payment_date and p.payment_date.year == int(year) and p.payment_date.month == int(month):
                total += p.amount
        return total

    def action_transfer_to_new_deposit(self):
        """ย้ายพนักงานไป deposit ของสาขา/แผนกปัจจุบัน — หยุดหักจาก deposit เก่า + carry-forward ที่ยังไม่หัก"""
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            raise UserError("ไม่มีข้อมูลพนักงาน")
        if not emp.branch_id or not emp.department_id:
            raise UserError("พนักงานต้องมีสาขาและแผนกปัจจุบัน")
        if (emp.branch_id == self.deposit_id.branch_id
                and emp.department_id in self.deposit_id.department_ids):
            raise UserError("สาขา/แผนกปัจจุบันของพนักงานยังอยู่ใน deposit นี้ ไม่ต้องย้าย")
        if self.work_status != 'working':
            raise UserError("ย้ายได้เฉพาะ line ที่สถานะ 'ทำงานอยู่' เท่านั้น")
        # หา deposit ของสาขา/แผนกใหม่ (ที่มี department_id ของพนักงานอยู่)
        target_deposit = self.env['work.security.deposit'].sudo().search([
            ('branch_id', '=', emp.branch_id.id),
            ('department_ids', 'in', emp.department_id.id),
        ], limit=1)
        if not target_deposit:
            raise UserError(
                "ไม่พบ deposit ของสาขา '%s' / แผนก '%s' — กรุณาสร้างก่อน" % (
                    emp.branch_id.name, emp.department_id.name,
                ))
        # ตรวจว่าพนักงานยังไม่มี active line ใน target deposit
        existing_in_target = target_deposit.line_ids.filtered(
            lambda l: l.employee_id == emp and l.work_status == 'working'
        )
        if existing_in_target:
            raise UserError(
                "พนักงาน '%s' อยู่ใน deposit '%s' [#%s] แล้ว (สถานะ: ทำงานอยู่) — ไม่สามารถย้ายซ้ำได้" % (
                    emp.firstname or '', target_deposit.name, target_deposit.id,
                ))
        # คำนวณ payment_ids ที่ยังไม่ได้หัก (carry-forward)
        unsynced = self.payment_ids.filtered(lambda p: not p.is_synced)
        carry_cmds = []
        today = fields.Date.context_today(self)
        for p in unsynced.sorted('payment_date'):
            if p.payment_date and p.payment_date >= today:
                carry_cmds.append((0, 0, {
                    'payment_date': p.payment_date,
                    'amount': p.amount,
                }))
        # สร้าง line ใหม่ใน deposit ใหม่
        new_line = self.env['work.security.deposit.line'].sudo().create({
            'deposit_id': target_deposit.id,
            'employee_id': emp.id,
            'start_work_date': self.start_work_date,
            'total_amount': self.total_amount,
            'work_status': 'working',
            'payment_ids': carry_cmds,
            'transferred_from_line_id': self.id,
        })
        # ปิด line เก่า
        self.write({
            'work_status': 'transferred',
            'transferred_date': today,
            'transferred_to_line_id': new_line.id,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ย้ายไป deposit ใหม่สำเร็จ',
                'message': 'พนักงาน %s ถูกย้ายไป deposit "%s" แล้ว (carry %d รอบ)' % (
                    emp.firstname or '', target_deposit.name, len(carry_cmds),
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_mark_as_historical(self):
        """ทำเครื่องหมายว่าพนักงานคนนี้หักครบไปแล้ว (เศษย้อนหลัง — ก่อนใช้ระบบนี้)
        ตั้ง is_synced=True สำหรับทุก payment ที่ payment_date <= วันนี้ โดยไม่ผูก payroll_id"""
        today = fields.Date.context_today(self)
        for rec in self:
            past_payments = rec.payment_ids.filtered(
                lambda p: p.payment_date and p.payment_date <= today and not p.is_synced
            )
            if past_payments:
                past_payments.write({'is_synced': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ทำเครื่องหมายหักครบเศษย้อนหลัง',
                'message': 'ตั้งเป็น "หักแล้ว" สำหรับ %d รายการ' % len(self),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_schedule(self):
        """เปิด form view ของ line นี้ (มีตารางการหักให้แก้)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'ตารางการหัก - %s' % (self.employee_id.firstname or ''),
            'res_model': 'work.security.deposit.line',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'employee_salary.view_work_security_deposit_line_form').id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }


class WorkSecurityDepositLinePayment(models.Model):
    _name = 'work.security.deposit.line.payment'
    _description = 'รายการหักรายเดือน (เงินประกันการทำงาน)'
    _order = 'payment_date'

    line_id = fields.Many2one('work.security.deposit.line', string='พนักงาน',
                              required=True, ondelete='cascade', index=True)
    deposit_state = fields.Selection(related='line_id.deposit_id.state', store=True, readonly=True)
    payment_type = fields.Selection([
        ('regular', 'หักรายเดือน (ทั่วไป)'),
        ('work_permit_fee', 'ค่าธรรมเนียมต่อใบอนุญาตทำงาน'),
        ('visa_fee', 'ค่าธรรมเนียมวีซ่า (Visa)'),
        ('document_service', 'ค่าบริการทำเอกสาร'),
        ('other', 'อื่นๆ'),
    ], string='ประเภท', default='regular', required=True)
    payment_date = fields.Date(string='เดือนที่หัก', required=True,
                               help='เลือกวันใดวันหนึ่งของเดือนที่จะหัก ระบบใช้เดือน/ปีของวันนี้')
    amount = fields.Float(string='จำนวนเงิน (บาท)', required=True, default=0.0)
    is_synced = fields.Boolean(string='ส่งเข้า Payroll แล้ว', default=False, readonly=True)
    payroll_id = fields.Many2one('payroll.salary', string='Payroll', readonly=True, ondelete='set null')
    display_status = fields.Selection([
        ('pending', 'รอหัก'),
        ('deducted', 'หักแล้ว'),
        ('cancelled', 'ยกเลิก (ออกจากงาน)'),
        ('refunded', 'หักแล้ว → คืนแล้ว'),
        ('transferred', 'ย้าย (ไป deposit ใหม่)'),
    ], string='สถานะ', compute='_compute_display_status', store=True)

    @api.depends('is_synced', 'payment_date', 'payment_type',
                 'line_id.work_status', 'line_id.resign_date', 'line_id.refund_status',
                 'line_id.transferred_date')
    def _compute_display_status(self):
        for rec in self:
            line = rec.line_id
            if line and line.work_status == 'transferred' and line.transferred_date:
                if rec.payment_date and rec.payment_date > line.transferred_date:
                    rec.display_status = 'transferred'
                elif rec.is_synced:
                    rec.display_status = 'deducted'
                else:
                    rec.display_status = 'pending'
            elif line and line.work_status == 'resigned' and line.resign_date:
                if rec.payment_date and rec.payment_date > line.resign_date:
                    rec.display_status = 'cancelled'
                elif (rec.is_synced and rec.payment_type == 'regular'
                      and line.refund_status == 'refunded'):
                    rec.display_status = 'refunded'
                elif rec.is_synced:
                    rec.display_status = 'deducted'
                else:
                    rec.display_status = 'pending'
            elif rec.is_synced:
                rec.display_status = 'deducted'
            else:
                rec.display_status = 'pending'

    @api.constrains('amount', 'payment_type')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError("จำนวนเงินที่หักห้ามติดลบ")
            # บังคับ > 0 เฉพาะหักรายเดือน (regular) — work_permit ปล่อยให้ user กรอกทีหลังได้
            if rec.payment_type == 'regular' and rec.amount <= 0:
                raise ValidationError(
                    "จำนวนเงินที่หักของแต่ละเดือนต้องมากกว่า 0 (สำหรับ 'หักรายเดือน')"
                )

    # ============================================================
    # ติ๊ก/ยกเลิก "หักแล้ว" รายแถว (สำหรับยอดที่หักไปแล้วนอกระบบทำเงินเดือน)
    # ============================================================
    def action_mark_deducted(self):
        """ทำเครื่องหมาย "หักแล้ว" เฉพาะแถวนี้ — ใช้กับยอดที่หักจากพนักงานไปแล้ว
        "นอกระบบ" (เช่น หักสด/หักก่อนเริ่มใช้ระบบทำเงินเดือน)

        ต่างจากปุ่ม "ตั้งเป็นหักครบแล้ว (พนักงานเก่า)" ที่ mark ทุกแถว <= วันนี้แบบเหมารวม:
        ปุ่มนี้ mark ทีละแถวที่เลือก จึงเว้นแถวที่ยังต้องให้ payroll หักจริงไว้ได้
        (is_synced=True, payroll_id ว่าง = เศษ/นอกระบบ → นับรวมตอนคืนเงินลาออก แต่ไม่ผูก payroll)
        """
        for rec in self:
            if not rec.is_synced:
                rec.write({'is_synced': True})
        self.mapped('line_id')._compute_resign_info()
        return True

    def action_unmark_deducted(self):
        """ยกเลิกเครื่องหมาย "หักแล้ว" เฉพาะแถวนี้ — เฉพาะแถวที่ยังไม่ผูก payroll จริง
        (กันยกเลิกยอดที่หักผ่านการทำเงินเดือนไปแล้ว — ต้องไปแก้ที่หน้า payroll แทน)"""
        for rec in self:
            if rec.payroll_id:
                raise UserError(
                    "แถววันที่ %s ถูกหักผ่านการทำเงินเดือนแล้ว (%s) — "
                    "ไม่สามารถยกเลิกที่นี่ได้ กรุณาแก้ที่หน้าทำเงินเดือน" % (
                        rec.payment_date and rec.payment_date.strftime('%d/%m/%Y') or '-',
                        rec.payroll_id.display_name,
                    ))
            if rec.is_synced:
                rec.write({'is_synced': False})
        self.mapped('line_id')._compute_resign_info()
        return True



class WorkSecurityDepositDefaultPayment(models.Model):
    _name = 'work.security.deposit.default.payment'
    _description = 'ค่าเริ่มต้น: หักยอดต่อเดือน (ระดับ deposit)'
    _order = 'month_index'

    deposit_id = fields.Many2one('work.security.deposit', string='รายการ',
                                 required=True, ondelete='cascade', index=True)
    month_index = fields.Integer(string='เดือนที่', required=True)
    amount = fields.Float(string='จำนวนเงิน (บาท)', required=True, default=0.0)

    _sql_constraints = [
        ('uniq_month_per_deposit', 'unique(deposit_id, month_index)',
         'ห้ามตั้งค่าเริ่มต้นของเดือนเดียวกันซ้ำ'),
    ]

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError("ยอดหักต่อเดือนห้ามติดลบ")

    @api.constrains('month_index')
    def _check_month_index(self):
        for rec in self:
            if rec.month_index <= 0:
                raise ValidationError("เดือนที่ต้องเป็นเลขจำนวนเต็มบวก")


class EmployeeSalaryInherit(models.Model):
    """เพิ่มข้อมูลออกจากงาน + ประวัติเงินประกันการทำงานบน employee.salary"""
    _inherit = 'employee.salary'

    resign_date = fields.Date(string='วันที่ออกจากงาน',
                              help='วันที่พนักงานออกจากงาน — ใช้คำนวณการคืนเงินประกันการทำงาน')
    deposit_line_ids = fields.One2many(
        'work.security.deposit.line', 'employee_id',
        string='ประวัติเงินประกันการทำงาน',
        readonly=True,
    )
    deposit_total_deducted = fields.Float(
        string='หักไปแล้ว (รวม บาท)', compute='_compute_deposit_totals',
    )
    deposit_total_refund = fields.Float(
        string='ต้องคืน (รวม บาท)', compute='_compute_deposit_totals',
        help='ผลรวมเงินที่หักไปแล้วของรายการที่สถานะ "ออกจากงาน" — เงินที่ต้องคืนพนักงาน',
    )
    deposit_refund_status = fields.Selection([
        ('none', 'ไม่ต้องคืน'),
        ('pending', 'รอคืนเงิน'),
        ('refunded', 'คืนแล้ว'),
    ], string='สถานะการคืนเงิน', compute='_compute_deposit_refund_status')

    @api.depends('deposit_line_ids', 'deposit_line_ids.refund_amount',
                 'deposit_line_ids.work_status', 'deposit_line_ids.state')
    def _compute_deposit_totals(self):
        for rec in self:
            confirmed = rec.deposit_line_ids.filtered(lambda l: l.state == 'confirmed')
            rec.deposit_total_deducted = sum(confirmed.mapped('refund_amount'))
            resigned = confirmed.filtered(lambda l: l.work_status == 'resigned')
            rec.deposit_total_refund = sum(resigned.mapped('refund_amount'))

    @api.depends('deposit_line_ids.refund_status', 'deposit_line_ids.state')
    def _compute_deposit_refund_status(self):
        for rec in self:
            confirmed = rec.deposit_line_ids.filtered(lambda l: l.state == 'confirmed')
            statuses = set(confirmed.mapped('refund_status'))
            if 'pending' in statuses:
                rec.deposit_refund_status = 'pending'
            elif 'refunded' in statuses:
                rec.deposit_refund_status = 'refunded'
            else:
                rec.deposit_refund_status = 'none'

    def write(self, vals):
        res = super().write(vals)
        if 'resign_date' in vals:
            for emp in self:
                if emp.resign_date:
                    for line in emp.deposit_line_ids:
                        if line.work_status != 'resigned' or line.resign_date != emp.resign_date:
                            line.sudo().write({
                                'resign_date': emp.resign_date,
                                'work_status': 'resigned',
                            })
                # ✅ auto-trigger: recompute payroll ของพนักงานคนนี้ ตามรอบที่เกี่ยวข้อง
                # → calculate_lateness.php จะได้ resign_date ล่าสุด ไม่นับวันหลังลาออกเป็นขาด
                emp._recompute_payroll_for_resign()
        return res

    def _recompute_payroll_for_resign(self):
        """recompute payroll.salary ของพนักงาน หลังแก้ resign_date

        Scope: เฉพาะรอบที่ "วันสิ้นรอบ >= resign_date" (รอบที่อาจมีวันหลังลาออก)
        - resign_date มีค่า → recompute เฉพาะรอบที่เกี่ยวข้อง (เร็ว ไม่แตะรอบเก่า)
        - resign_date ถูกล้าง (ยกเลิกลาออก) → recompute ทุกรอบ non-manual (คืนค่าให้นับขาดปกติ)
        ข้าม payroll ที่ manual_override (เคารพการปรับมือ)
        """
        Payroll = self.env['payroll.salary']
        for emp in self:
            rdate = emp.resign_date
            payrolls = Payroll.search([('employee_id', '=', emp.id)])
            recomputed = 0
            for p in payrolls:
                if p.manual_override:
                    continue
                if rdate:
                    try:
                        py, pm = int(p.year), int(p.month)
                        last = calendar.monthrange(py, pm)[1]
                        cycle_end = date(py, pm, min(p.cutoff_day or 24, last))
                    except (ValueError, TypeError):
                        cycle_end = None
                    # รอบที่สิ้นก่อนวันลาออก → พนักงานทำงานเต็มรอบ ไม่ต้อง recompute
                    if cycle_end and cycle_end < rdate:
                        continue
                p._populate_all_lines()
                recomputed += 1
            _logger.info(
                "[RESIGN-SYNC] emp=%s resign_date=%s → recompute payroll %d รายการ",
                emp.employee_code or '-', rdate or '-', recomputed)


class PayrollSalaryInherit(models.Model):
    """Hook payroll.salary.expense_insurance ให้ดึงจาก work.security.deposit อัตโนมัติ
    และ mark payment ของ work.security.deposit.line.payment ที่ตรงกัน เป็น synced"""
    _inherit = 'payroll.salary'

    expense_insurance_locked = fields.Boolean(
        string='ยอดประกันการทำงานถูกล็อกจากเมนูจัดการเงินประกัน',
        compute='_compute_expense_insurance_locked',
        help='True เมื่อพนักงานมี work.security.deposit ที่ confirmed ครอบคลุมเดือน/ปีนี้ → '
             'แก้ยอดได้เฉพาะที่หน้าจัดการเงินประกันการทำงาน',
    )

    @api.depends('employee_id', 'month', 'year')
    def _compute_expense_insurance_locked(self):
        DepositLine = self.env['work.security.deposit.line'].sudo()
        for rec in self:
            if not rec.employee_id or not rec.month or not rec.year:
                rec.expense_insurance_locked = False
                continue
            lines = DepositLine.search([
                ('employee_id', '=', rec.employee_id.id),
                ('deposit_id.state', '=', 'confirmed'),
            ])
            # ✅ ใช้ 'รอบตัด 25–24' ให้ตรงกับการคำนวณยอดหัก ใน _compute_deposit_amounts
            cyc_start, cyc_end = rec._security_deposit_cycle_window()
            locked = False
            for line in lines:
                # ครอบคลุมรอบนี้ ถ้ามี payment_date ในรอบ หรือ resign ตกในรอบ (cutoff cycle)
                if (line.work_status == 'resigned' and line.resign_date
                        and cyc_start and cyc_end
                        and cyc_start <= line.resign_date <= cyc_end):
                    locked = True
                    break
                if cyc_start and cyc_end:
                    for p in line.payment_ids:
                        if p.payment_date and cyc_start <= p.payment_date <= cyc_end:
                            locked = True
                            break
                if locked:
                    break
            rec.expense_insurance_locked = locked

    def _refresh_security_deposit(self):
        Payment = self.env['work.security.deposit.line.payment'].sudo()
        DepositLine = self.env['work.security.deposit.line'].sudo()
        for rec in self:
            if not rec.employee_id or not rec.month or not rec.year:
                _logger.info("[DEPOSIT_HOOK] Skip — missing emp/month/year (emp=%s, m=%s, y=%s)",
                             rec.employee_id and rec.employee_id.employee_code, rec.month, rec.year)
                continue
            _logger.info("[DEPOSIT_HOOK] Run for payroll emp=%s month=%s year=%s",
                         rec.employee_id.employee_code, rec.month, rec.year)

            # ✅ ใช้ 'รอบตัด 25–24' (cutoff cycle) ทั้งการคืนเงินและหัก work_permit
            cyc_start, cyc_end = rec._security_deposit_cycle_window()

            # 1) ตรวจ "ลาออกในรอบนี้" — ถ้าตกในรอบตัดของ payroll นี้ → คืนเงินที่หักไปแล้วทั้งหมด
            resigned_lines = DepositLine.search([
                ('employee_id', '=', rec.employee_id.id),
                ('deposit_id.state', '=', 'confirmed'),
                ('work_status', '=', 'resigned'),
                ('resign_date', '!=', False),
            ])
            resigned_in_period = resigned_lines.filtered(
                lambda l: cyc_start and cyc_end
                          and cyc_start <= l.resign_date <= cyc_end
            )
            if resigned_in_period:
                # 1) คืนเฉพาะ regular ที่ synced แล้ว
                total_refund = 0.0
                for line in resigned_in_period:
                    paid = line.payment_ids.filtered(
                        lambda p: p.is_synced and p.payment_type == 'regular'
                    )
                    total_refund += sum(paid.mapped('amount'))
                # 2) หัก work_permit ที่ตกในเดือน resign (ไม่คืน — หักรวมไปกับการ refund)
                #    ต้องใช้ work_permit_payment_ids เพราะ payment_ids มี domain filter regular เท่านั้น
                wp_deduction = 0.0
                matched_wp = Payment
                for line in resigned_in_period:
                    wp = line.work_permit_payment_ids.filtered(
                        lambda p: p.payment_date
                                  and cyc_start <= p.payment_date <= cyc_end
                    )
                    if line.resign_date:
                        wp = wp.filtered(lambda p: p.payment_date <= line.resign_date)
                    wp_deduction += sum(wp.mapped('amount'))
                    matched_wp |= wp
                # Net: work_permit deduction - regular refund
                new_val = wp_deduction - total_refund
                if abs((rec.expense_insurance or 0.0) - new_val) > 0.005:
                    _logger.info(
                        "[DEPOSIT_HOOK] RESIGN refund emp=%s month=%s/%s refund=%.2f wp_deduction=%.2f net=%.2f",
                        rec.employee_id.employee_code, rec.month, rec.year,
                        total_refund, wp_deduction, new_val,
                    )
                    rec.expense_insurance = new_val
                # mark synced ของ work_permit ที่ตกในเดือนนี้ (เฉพาะ payroll ที่ save แล้ว และยังไม่ sync)
                if isinstance(rec.id, int):
                    to_sync = matched_wp.filtered(
                        lambda p: not p.is_synced or p.payroll_id.id != rec.id
                    )
                    if to_sync:
                        to_sync.write({'is_synced': True, 'payroll_id': rec.id})
                    # mark refund_payroll_id (เฉพาะ line ที่ยังไม่ตรง)
                    lines_to_update = resigned_in_period.filtered(
                        lambda l: l.refund_payroll_id.id != rec.id
                    )
                    if lines_to_update:
                        lines_to_update.write({'refund_payroll_id': rec.id})
                continue

            # 2) หักปกติของรอบนี้ (ใช้ cutoff cycle เหมือน _compute_deposit_amounts)
            payments = Payment.search([
                ('line_id.employee_id', '=', rec.employee_id.id),
                ('line_id.deposit_id.state', '=', 'confirmed'),
            ])
            total = 0.0
            matched = Payment
            for p in payments:
                line = p.line_id
                if (line.work_status == 'resigned' and line.resign_date
                        and p.payment_date and p.payment_date > line.resign_date):
                    continue
                if (p.payment_date and cyc_start and cyc_end
                        and cyc_start <= p.payment_date <= cyc_end):
                    total += p.amount
                    matched |= p
            if total and abs((rec.expense_insurance or 0.0) - total) > 0.005:
                _logger.info(
                    "[DEPOSIT_HOOK] NORMAL emp=%s month=%s/%s total=%.2f (was %.2f)",
                    rec.employee_id.employee_code, rec.month, rec.year,
                    total, rec.expense_insurance or 0.0,
                )
                rec.expense_insurance = total
            # mark synced เฉพาะ payment ที่ยังไม่ sync (กัน loop)
            if matched and isinstance(rec.id, int):
                to_sync = matched.filtered(
                    lambda p: not p.is_synced or p.payroll_id.id != rec.id
                )
                if to_sync:
                    to_sync.write({'is_synced': True, 'payroll_id': rec.id})
                    to_sync.mapped('line_id')._compute_resign_info()

    def _populate_all_lines(self):
        # ⚠️ DEPRECATED hook: เลิกเขียน expense_insurance แล้ว
        # ตอนนี้ deposit ถูกดึงผ่าน computed fields (expense_deposit_regular_total, ฯลฯ)
        # ที่ contribute เข้า expense_other / income_other โดยตรง
        # เก็บ _refresh_security_deposit ไว้สำหรับ mark is_synced + refund_payroll_id
        if self.env.context.get('skip_security_deposit_hook'):
            return super(PayrollSalaryInherit, self)._populate_all_lines()
        self.with_context(skip_security_deposit_hook=True)._refresh_security_deposit_meta()
        return super(PayrollSalaryInherit, self)._populate_all_lines()

    @api.model_create_multi
    def create(self, vals_list):
        """หลัง save → mark is_synced + refund_payroll_id ของ deposit payments ที่ตรงเดือนนี้"""
        payrolls = super(PayrollSalaryInherit, self).create(vals_list)
        if payrolls:
            payrolls.with_context(skip_security_deposit_hook=True)._refresh_security_deposit_meta()
        return payrolls

    def _refresh_security_deposit_meta(self):
        """Mark is_synced + refund_payroll_id เท่านั้น (ไม่เขียน expense_insurance อีกแล้ว)"""
        Payment = self.env['work.security.deposit.line.payment'].sudo()
        DepositLine = self.env['work.security.deposit.line'].sudo()
        for rec in self:
            if not rec.employee_id or not rec.month or not rec.year or not isinstance(rec.id, int):
                continue
            try:
                m = int(rec.month)
                y = int(rec.year)
                last_day = calendar.monthrange(y, m)[1]
                start_d = date(y, m, 1)
                end_d = date(y, m, last_day)
            except (ValueError, TypeError):
                continue

            # mark payments ที่ตกในรอบนี้ → is_synced + payroll_id
            # ✅ ใช้ 'รอบตัด 25–24' (cutoff cycle) ให้ตรงกับการคำนวณยอดหัก ใน _compute_deposit_amounts
            cyc_start, cyc_end = rec._security_deposit_cycle_window()
            if not cyc_start or not cyc_end:
                cyc_start, cyc_end = start_d, end_d
            payments_in_month = Payment.search([
                ('line_id.employee_id', '=', rec.employee_id.id),
                ('line_id.deposit_id.state', '=', 'confirmed'),
                ('payment_date', '>=', cyc_start),
                ('payment_date', '<=', cyc_end),
            ])
            payments_in_month = payments_in_month.filtered(
                lambda p: not (p.line_id.work_status == 'resigned' and p.line_id.resign_date
                               and p.payment_date > p.line_id.resign_date)
            )
            to_sync = payments_in_month.filtered(
                lambda p: not p.is_synced or p.payroll_id.id != rec.id
            )
            if to_sync:
                to_sync.write({'is_synced': True, 'payroll_id': rec.id})

            # mark refund_payroll_id ของ lines ที่ลาออกในรอบนี้ (ใช้ cutoff cycle เหมือนการหัก)
            # ★ ข้าม line ที่ mark manual_refunded แล้ว
            resigned_lines = DepositLine.search([
                ('employee_id', '=', rec.employee_id.id),
                ('deposit_id.state', '=', 'confirmed'),
                ('work_status', '=', 'resigned'),
                ('resign_date', '>=', cyc_start),
                ('resign_date', '<=', cyc_end),
                ('manual_refunded', '=', False),
            ])
            lines_to_update = resigned_lines.filtered(
                lambda l: l.refund_payroll_id.id != rec.id
            )
            if lines_to_update:
                lines_to_update.write({'refund_payroll_id': rec.id})

    def unlink(self):
        """ลบ payroll → ปลด is_synced + payroll_id ของ payment ที่เคย sync เข้า payroll นี้
        + clear refund_payroll_id ของ deposit line ที่ถูก payroll นี้คืนเงิน
        + recompute เดือนที่หักไปแล้ว/เงินที่ต้องคืน บน line ที่เกี่ยวข้อง"""
        affected_lines = self.env['work.security.deposit.line']
        if self.ids:
            Payment = self.env['work.security.deposit.line.payment'].sudo()
            DepositLine = self.env['work.security.deposit.line'].sudo()
            payments = Payment.search([('payroll_id', 'in', self.ids)])
            if payments:
                affected_lines |= payments.mapped('line_id')
                payments.write({'is_synced': False, 'payroll_id': False})
            refund_lines = DepositLine.search([('refund_payroll_id', 'in', self.ids)])
            if refund_lines:
                affected_lines |= refund_lines
                refund_lines.write({'refund_payroll_id': False})
        res = super(PayrollSalaryInherit, self).unlink()
        if affected_lines:
            affected_lines._compute_resign_info()
        return res

    def name_get(self):
        """แสดงชื่อ payroll record ให้อ่านง่ายขึ้น เช่น 'สมชาย - 06/2026'
        แทนที่จะเป็น 'payroll.salary,289'"""
        result = []
        for rec in self:
            emp = rec.employee_id
            parts = []
            if emp:
                name = ' '.join(filter(None, [emp.firstname, emp.lastname]))
                if name:
                    parts.append(name)
            if rec.month and rec.year:
                parts.append('%02d/%s' % (rec.month, rec.year))
            label = ' - '.join(parts) if parts else ('Payroll #%d' % rec.id)
            result.append((rec.id, label))
        return result


class WorkSecurityDepositAddWizard(models.TransientModel):
    _name = 'work.security.deposit.add.wizard'
    _description = 'เลือกพนักงานเพิ่มเข้าทำเงินประกัน'

    deposit_id = fields.Many2one('work.security.deposit', string='รายการ', required=True)
    candidate_employee_ids = fields.Many2many(
        'employee.salary', 'wsd_add_wizard_candidate_rel',
        string='พนักงานใหม่ทั้งหมด', readonly=True,
        help='พนักงานใหม่ในสาขา/แผนกนี้ที่ยังไม่อยู่ในตาราง')
    employee_ids = fields.Many2many(
        'employee.salary', 'wsd_add_wizard_selected_rel',
        string='เลือกพนักงานที่จะเพิ่ม',
        help='ติ๊กเฉพาะคนที่ต้องการเพิ่มเข้าทำเงินประกันการทำงาน')

    def action_add_selected(self):
        """เพิ่มเฉพาะพนักงานที่เลือก เข้า deposit"""
        self.ensure_one()
        count = self.deposit_id._add_employees_to_deposit(self.employee_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'เพิ่มพนักงาน',
                'message': 'เพิ่มพนักงานเข้าตาราง %d คน' % count,
                'type': 'success' if count else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
