# -*- coding: utf-8 -*-
"""กำหนดสูตรคิด "สาย" เองได้ พร้อมวันเริ่มใช้

เดิมสูตรถูกฝังไว้ตายตัว = ผ่อนผัน 15 นาที (เกิน 15 นาทีถือว่าสาย และนับตั้งแต่
นาทีแรกรวม 15 นาทีที่ผ่อนผันด้วย) โมดูลนี้ให้ตั้งเองได้ว่า

* ผ่อนผันกี่นาที (ใส่ 0 = ไม่ผ่อนผันเลย) หรือ
* ไม่ผ่อนผัน แต่กำหนด "เวลาเข้างานล่าสุด" เป็นเวลานาฬิกา เช่น 08:00

และที่สำคัญคือกำหนด **วันเริ่มใช้** ได้ เพื่อไม่ให้กระทบยอดที่คำนวณไปแล้ว
เอกสารวันก่อนวันเริ่มใช้ยังคิดด้วยสูตรเดิมทุกประการ

การตัดสินใจว่าวันไหนใช้สูตรอะไร ทำฝั่ง PHP (calculate_lateness.php) เพราะเป็น
ที่ที่วนคำนวณรายวัน — Odoo แค่ส่ง "รายการสูตรทั้งหมด" ไปให้เลือกใช้เอง
ทำให้รอบเงินเดือนที่คร่อมวันเริ่มใช้ (เช่น ตัดรอบ 25 ส.ค. - 24 ก.ย. แต่เริ่มใช้ 1 ก.ย.)
คิดถูกทั้งสองช่วงในใบเดียว
"""

import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ค่าที่ระบบใช้มาแต่เดิม ถ้ายังไม่เคยตั้งสูตรอะไรเลย
LEGACY_GRACE_MINUTES = 15

MODE_GRACE = 'grace'
MODE_DEADLINE = 'deadline'


class PayrollLatenessRule(models.Model):
    _name = 'payroll.lateness.rule'
    _description = 'สูตรคิดสาย (ผ่อนผันเข้างาน)'
    _order = 'effective_date desc, id desc'
    _rec_name = 'display_summary'

    effective_date = fields.Date(
        string='เริ่มใช้ตั้งแต่วันที่',
        required=True,
        default=fields.Date.context_today,
        help='สูตรนี้จะใช้กับการลงเวลาตั้งแต่วันที่นี้เป็นต้นไป\n'
             'วันก่อนหน้านี้ยังคิดด้วยสูตรเดิม จึงไม่กระทบยอดที่คำนวณไปแล้ว',
    )
    mode = fields.Selection(
        [
            (MODE_GRACE, 'ผ่อนผันเป็นนาที (เลทได้)'),
            (MODE_DEADLINE, 'ไม่ผ่อนผัน — กำหนดเวลาเข้างานล่าสุด'),
        ],
        string='รูปแบบ',
        required=True,
        default=MODE_GRACE,
    )
    grace_minutes = fields.Integer(
        string='ผ่อนผันได้ (นาที)',
        default=LEGACY_GRACE_MINUTES,
        help='เข้างานช้าไม่เกินกี่นาทีถึงจะยังไม่ถือว่าสาย\n'
             'ใส่ 0 = ไม่ผ่อนผันเลย สายทันทีที่เลยเวลาเข้ากะ\n'
             'หมายเหตุ: ถ้าเกินที่ผ่อนผัน จะนับสายตั้งแต่นาทีแรก '
             '(รวมนาทีที่ผ่อนผันด้วย) เหมือนสูตรเดิม',
    )
    deadline_hour = fields.Float(
        string='เข้างานไม่เกินเวลา',
        default=8.0,
        help='เข้างานได้ช้าที่สุดถึงเวลานี้ เลยจากนี้ถือว่าสาย (ปกติ 08:00)',
    )
    branch_ids = fields.Many2many(
        'hr.branch.custom',
        'payroll_lateness_rule_branch_rel', 'rule_id', 'branch_id',
        string='ใช้กับสาขา',
        help='เว้นว่าง = ใช้กับทุกสาขา\n'
             'ถ้าเลือกสาขา จะใช้เฉพาะพนักงานในสาขานั้น\n'
             'สาขาที่ระบุจะชนะสูตร "ทุกสาขา" ที่เริ่มใช้วันเดียวกัน',
    )
    branch_scope = fields.Char(
        string='ขอบเขต', compute='_compute_display_summary', store=True)
    note = fields.Char(string='หมายเหตุ')
    # ไม่มีฟิลด์ active โดยตั้งใจ — ถ้าจะกลับไปใช้สูตรเดิม ให้ "เพิ่มสูตรใหม่"
    # ที่มีวันเริ่มใช้ถัดไปแทน จะได้ไม่ไปแก้ผลการคำนวณของวันที่ผ่านมาแล้ว

    display_summary = fields.Char(
        string='สูตร', compute='_compute_display_summary', store=True)

    # ------------------------------------------------------------------
    @api.depends('mode', 'grace_minutes', 'deadline_hour', 'effective_date', 'branch_ids')
    def _compute_display_summary(self):
        for rule in self:
            if rule.mode == MODE_DEADLINE:
                detail = _('เข้างานไม่เกิน %s') % rule._deadline_text()
            elif rule.grace_minutes > 0:
                detail = _('ผ่อนผัน %s นาที') % rule.grace_minutes
            else:
                detail = _('ไม่ผ่อนผัน')
            scope = (', '.join(rule.branch_ids.mapped('name'))
                     if rule.branch_ids else _('ทุกสาขา'))
            rule.branch_scope = scope
            date_text = fields.Date.to_string(rule.effective_date) or '-'
            rule.display_summary = '%s — %s (เริ่ม %s)' % (detail, scope, date_text)

    def _deadline_text(self):
        self.ensure_one()
        total = int(round((self.deadline_hour or 0.0) * 60))
        return '%02d:%02d' % (total // 60, total % 60)

    @api.constrains('grace_minutes', 'deadline_hour', 'mode')
    def _check_values(self):
        for rule in self:
            if rule.mode == MODE_GRACE and rule.grace_minutes < 0:
                raise ValidationError(_('นาทีผ่อนผันต้องไม่ติดลบ'))
            if rule.mode == MODE_DEADLINE and not (0.0 <= rule.deadline_hour < 24.0):
                raise ValidationError(_('เวลาเข้างานล่าสุดต้องอยู่ระหว่าง 00:00 - 23:59'))

    @api.constrains('effective_date', 'branch_ids')
    def _check_no_overlap(self):
        """วันเริ่มใช้เดียวกัน ห้ามมีสูตรที่ขอบเขตสาขาทับกัน ไม่งั้นไม่รู้จะใช้อันไหน

        อนุญาต: 01/09 "ทุกสาขา" + 01/09 "ภูเก็ต"  (ภูเก็ตชนะเฉพาะสาขาตัวเอง)
        ห้าม:    01/09 "ภูเก็ต"   + 01/09 "ภูเก็ต, ชะอำ"
        ห้าม:    01/09 "ทุกสาขา"  + 01/09 "ทุกสาขา"
        """
        for rule in self:
            others = self.search([
                ('effective_date', '=', rule.effective_date),
                ('id', '!=', rule.id),
            ])
            for other in others:
                if not rule.branch_ids and not other.branch_ids:
                    raise ValidationError(_(
                        'มีสูตร "ทุกสาขา" ที่เริ่มใช้วันที่ %s อยู่แล้ว '
                        '— แก้ไขรายการเดิม หรือระบุสาขาให้ต่างกัน'
                    ) % fields.Date.to_string(rule.effective_date))
                overlap = rule.branch_ids & other.branch_ids
                if overlap:
                    raise ValidationError(_(
                        'สาขา %s ถูกกำหนดไว้ 2 สูตรในวันเริ่มใช้เดียวกัน (%s)'
                    ) % (', '.join(overlap.mapped('name')),
                         fields.Date.to_string(rule.effective_date)))

    # ------------------------------------------------------------------
    # ส่งให้ฝั่ง PHP ใช้เลือกสูตรรายวัน
    # ------------------------------------------------------------------
    @api.model
    def _rules_for_branch(self, branch=None):
        """สูตรที่ใช้ได้กับสาขานี้ เรียงตามวันเริ่มใช้ (เก่า -> ใหม่)

        คัดกรองฝั่ง Odoo เพราะสาขาของพนักงานอยู่ที่นี่ (payroll.salary.branch_id)
        PHP จึงไม่ต้องรู้เรื่องสาขาเลย — รับมาแค่รายการที่กรองแล้ว
        วันเริ่มใช้เดียวกัน "สาขาที่ระบุ" ชนะ "ทุกสาขา"
        """
        rules = self.sudo().search([], order='effective_date asc')
        by_date = {}
        for rule in rules:
            if rule.branch_ids and (not branch or branch not in rule.branch_ids):
                continue  # สูตรของสาขาอื่น
            current = by_date.get(rule.effective_date)
            # สูตรที่ระบุสาขา ชนะสูตรทุกสาขาที่เริ่มใช้วันเดียวกัน
            if current is None or (rule.branch_ids and not current.branch_ids):
                by_date[rule.effective_date] = rule
        return [by_date[d] for d in sorted(by_date)]

    @api.model
    def _rules_payload(self, branch=None):
        """แปลงสูตรของสาขานั้นเป็น payload ให้ PHP เลือกใช้รายวัน

        PHP จะเลือกสูตรที่ ``effective_date <= วันที่กำลังคำนวณ`` ตัวล่าสุด
        ถ้าไม่มีสูตรไหนครอบคลุม = ใช้สูตรเดิมที่ส่งไปทาง ``grace_period``
        """
        payload = []
        for rule in self._rules_for_branch(branch):
            payload.append({
                'effective_date': fields.Date.to_string(rule.effective_date),
                'mode': rule.mode,
                'grace_minutes': int(rule.grace_minutes or 0),
                'deadline_hour': float(rule.deadline_hour or 0.0),
            })
        return payload

    @api.model
    def _rule_for_date(self, date_value, branch=None):
        """สูตรที่มีผลกับวันที่นี้ของสาขานี้ (คืน None ถ้ายังไม่มีสูตรครอบคลุม)"""
        if not date_value:
            return None
        picked = None
        for rule in self._rules_for_branch(branch):
            if fields.Date.to_string(rule.effective_date) <= str(date_value):
                picked = rule
            else:
                break
        return picked

    # ------------------------------------------------------------------
    # หน้าจอ
    # ------------------------------------------------------------------
    @api.model
    def action_open_rules(self):
        """เมนู -> เด้ง popup รายการสูตร"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('กำหนดสูตรคิดสาย'),
            'res_model': self._name,
            'view_mode': 'tree,form',
            'target': 'new',
            'context': {'create': True},
        }

    # ------------------------------------------------------------------
    # API สำหรับแอปมือถือ (hrms_npd) — หน้าประวัติการลงเวลา
    # ------------------------------------------------------------------
    @api.model
    def api_get_late_minutes(self, employee_code, month, year):
        """คืนนาทีที่ "สาย" รายวันของเดือนนั้น ให้แอปเอาไปแสดงใต้เวลาเข้างาน

        เรียกจากแอปผ่าน JSON-RPC:
            callKw('payroll.lateness.rule', 'api_get_late_minutes',
                   [employee_code, month, year])

        ใช้ท่อเดียวกับตอนคิดเงินเดือนเป๊ะ ๆ คือยิงไป calculate_lateness.php
        พร้อมสูตรที่ตั้งไว้ + ตารางกะของพนักงาน ตัวเลขที่แอปโชว์จึงเป็น
        "นาทีเดียวกับที่ payroll หักจริง" ไม่ใช่คำนวณซ้ำในแอป
        และพอเปลี่ยนสูตรใน Odoo แอปก็ตามทันทีโดยไม่ต้องแก้แอป

        :return: {'YYYY-MM-DD': {'minutes': นาทีที่สาย, 'checkin': 'HH:MM'}}
                 เฉพาะวันที่สายจริง (ไม่สาย = ไม่มี key)

                 ที่ต้องคืน ``checkin`` มาด้วย เพราะวันหนึ่งสแกนเข้าได้หลายครั้ง
                 แต่ระบบคิดสายจาก "ครั้งแรกของวัน" ครั้งเดียว แอปจะได้เอาไป
                 จับคู่ว่าควรแสดงข้อความสายที่แถวไหน ไม่ใช่แปะทุกแถวของวันนั้น
        """
        import calendar

        from .payroll_salary import LATENESS_API_URL

        empty = {}
        if not employee_code:
            return empty
        try:
            month = int(month)
            year = int(year)
        except (TypeError, ValueError):
            return empty
        if not (1 <= month <= 12):
            return empty

        Employee = self.env['employee.salary'].sudo()
        employee = Employee.search([('employee_code', '=', employee_code)], limit=1)
        if not employee:
            return empty

        schedule = self.env['hr.work.schedule'].sudo().search(
            [('employee_id', '=', employee.id)], limit=1)
        if not schedule:
            # ยังไม่ได้ตั้งตารางกะ = คิดสายไม่ได้ ปล่อยว่างดีกว่าเดามั่ว
            _logger.info('[APP LATE] ไม่พบตารางกะของ %s', employee_code)
            return empty

        schedule_data = {}
        for dow in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat'):
            schedule_data['work_%s' % dow] = schedule['work_%s' % dow]
            schedule_data['%s_shift_start' % dow] = schedule['%s_shift_start' % dow]
            schedule_data['%s_shift_end' % dow] = schedule['%s_shift_end' % dow]

        holiday_template = self.env['payroll.holiday'].sudo().search(
            [('year', '=', year)], limit=1)
        holidays = ([line.date.strftime('%Y-%m-%d')
                     for line in holiday_template.line_ids]
                    if holiday_template else [])

        # cutoff_day = วันสุดท้ายของเดือน -> ฝั่ง PHP จะได้ช่วงที่คลุมทั้งเดือนปฏิทิน
        # (มีวันเกินมาต้นช่วงเล็กน้อย เดี๋ยวกรองออกตอนท้าย)
        last_day = calendar.monthrange(year, month)[1]

        payload = {
            'employee_code': employee_code,
            'grace_period': LEGACY_GRACE_MINUTES,
            'lateness_rules': self._rules_payload(employee.branch_id),
            'work_schedule': schedule_data,
            'month': month,
            'year': year,
            'cutoff_day': last_day,
            'official_holidays': holidays,
            'resign_date': (employee.resign_date.strftime('%Y-%m-%d')
                            if employee.resign_date else None),
            # ✅ ให้คิด "สายเข้างาน" ของวันนี้ด้วย พนักงานจะได้เห็นผลทันทีที่สแกนเข้า
            #    ไม่กระทบยอดหักเงิน เพราะฝั่ง PHP แยกไว้ ไม่บวกเข้ายอดรวม
            #    และ payroll ไม่ได้ส่ง flag นี้ จึงคิดเหมือนเดิมทุกประการ
            'include_today': True,
        }

        try:
            response = requests.post(LATENESS_API_URL, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            _logger.warning('[APP LATE] เรียก calculate_lateness ไม่สำเร็จ (%s): %s',
                            employee_code, exc)
            return empty

        if data.get('status') != 'success':
            _logger.warning('[APP LATE] API ตอบ error: %s', data.get('message'))
            return empty

        prefix = '%04d-%02d' % (year, month)
        result = {}
        for row in (data.get('debug') or {}).get('late_checkin_log') or []:
            day = row.get('date') or ''
            minutes = int(row.get('minutes') or 0)
            if minutes > 0 and day.startswith(prefix):
                result[day] = {
                    'minutes': minutes,
                    'checkin': row.get('checkin') or '',
                }
        return result

    def action_delete_rule(self):
        """ปุ่มถังขยะในตาราง

        ในหน้าต่าง popup ของ Odoo 14 เมนู ⚙ การดำเนินการ (ที่มีคำสั่ง "ลบ") ถูกซ่อน
        จึงต้องมีปุ่มลบของตัวเอง ไม่งั้นลบสูตรที่ตั้งผิดไม่ได้เลย
        ลบแล้วเปิด popup ใหม่เพื่อให้ตารางรีเฟรช
        """
        self.ensure_one()
        self.unlink()
        return self.action_open_rules()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
