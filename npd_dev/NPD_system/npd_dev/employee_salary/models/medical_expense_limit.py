# -*- coding: utf-8 -*-
"""วงเงินค่ารักษาพยาบาลต่อปี

ตั้งวงเงินได้ 2 ระดับ:
  1) วงเงินมาตรฐาน (ไม่ระบุพนักงาน) — ใช้กับพนักงานทุกคนในปีนั้น
  2) วงเงินเฉพาะราย (ระบุพนักงาน)  — ทับวงเงินมาตรฐานของปีเดียวกัน

การ "รีเซตเมื่อครบปี" ไม่ได้ลบยอดเก่าทิ้ง แต่นับวงเงินแยกตามปีของ
"วันที่ทำงาน" อยู่แล้ว (medical.expense.expense_year) พอขึ้นปีใหม่
ยอดใช้ไปจึงกลับไปเริ่มที่ 0 เอง ส่วน cron ด้านล่างทำหน้าที่ก๊อปปี้
ค่าวงเงินของปีก่อนมาตั้งเป็นปีใหม่ให้อัตโนมัติ จะได้ไม่ต้องมาตั้งเองทุกปี
"""
import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ใช้เมื่อยังไม่เคยตั้งวงเงินไว้เลย
DEFAULT_ANNUAL_LIMIT = 10000.0


class MedicalExpenseLimit(models.Model):
    _name = 'medical.expense.limit'
    _description = 'วงเงินค่ารักษาพยาบาลต่อปี'
    _order = 'year desc, employee_id'
    _rec_name = 'name'

    year = fields.Integer(
        string='ปี (ค.ศ.)',
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    employee_id = fields.Many2one(
        'employee.salary',
        string='พนักงาน',
        ondelete='cascade',
        help='เว้นว่าง = วงเงินมาตรฐานที่ใช้กับพนักงานทุกคนในปีนั้น\n'
             'ระบุพนักงาน = วงเงินเฉพาะรายคนนั้น (ทับวงเงินมาตรฐาน)',
    )
    employee_code = fields.Char(related='employee_id.employee_code',
                                string='รหัสพนักงาน', store=True, readonly=True)
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา',
                                related='employee_id.branch_id', store=True, readonly=True)
    amount = fields.Float(string='วงเงินต่อปี (บาท)', required=True,
                          default=DEFAULT_ANNUAL_LIMIT)
    note = fields.Char(string='หมายเหตุ')
    active = fields.Boolean(string='ใช้งาน', default=True)

    name = fields.Char(string='ชื่อ', compute='_compute_name', store=True)

    @api.depends('year', 'employee_id')
    def _compute_name(self):
        for rec in self:
            who = rec.employee_id.display_name if rec.employee_id else 'วงเงินมาตรฐาน (ทุกคน)'
            rec.name = '%s / ปี %s' % (who, rec.year or '-')

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if not rec.year or rec.year < 2000 or rec.year > 2999:
                raise ValidationError('กรุณากรอกปีเป็น ค.ศ. 4 หลัก เช่น 2026')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError('วงเงินต่อปีต้องไม่ติดลบ')

    @api.constrains('year', 'employee_id')
    def _check_unique_per_year(self):
        """กันตั้งวงเงินซ้ำ — 1 ปี ต่อ 1 พนักงาน (หรือ 1 วงเงินมาตรฐาน) เท่านั้น

        ใช้ constrains แทน SQL unique เพราะ Postgres ไม่ถือว่า NULL ซ้ำกัน
        (วงเงินมาตรฐานคือ employee_id เป็น NULL) จะกันซ้ำไม่ได้

        นับเฉพาะรายการที่ยังใช้งานอยู่ — ถ้า HR เก็บของเก่าเข้าคลัง (archive)
        แล้วตั้งใหม่ ต้องทำได้
        """
        for rec in self:
            domain = [
                ('year', '=', rec.year),
                ('employee_id', '=', rec.employee_id.id or False),
                ('id', '!=', rec.id),
            ]
            if self.sudo().search(domain, limit=1):
                who = rec.employee_id.display_name if rec.employee_id else 'วงเงินมาตรฐาน'
                raise ValidationError(
                    'มีวงเงินของ "%s" ปี %s อยู่แล้ว — แก้ไขรายการเดิมแทนการสร้างใหม่'
                    % (who, rec.year))

    # ============================================================
    # หาวงเงินที่ใช้จริงของพนักงาน 1 คนในปีที่ระบุ
    # ============================================================
    @api.model
    def get_limit_for(self, employee, year):
        """คืนวงเงินค่ารักษาพยาบาลของพนักงานคนนั้นในปีที่ระบุ

        ลำดับการค้นหา:
          1) วงเงินเฉพาะรายของปีนั้น
          2) วงเงินมาตรฐานของปีนั้น
          3) วงเงินมาตรฐานของปีล่าสุดที่ไม่เกินปีนั้น (กรณียังไม่ได้ตั้งปีใหม่)
          4) ค่า default 10,000 บาท
        """
        Limit = self.sudo()
        employee_id = employee.id if employee else False

        if employee_id:
            rec = Limit.search([
                ('year', '=', year),
                ('employee_id', '=', employee_id),
            ], limit=1)
            if rec:
                return rec.amount

        rec = Limit.search([
            ('year', '=', year),
            ('employee_id', '=', False),
        ], limit=1)
        if rec:
            return rec.amount

        rec = Limit.search([
            ('year', '<=', year),
            ('employee_id', '=', False),
        ], order='year desc', limit=1)
        if rec:
            return rec.amount

        return DEFAULT_ANNUAL_LIMIT

    # ============================================================
    # Cron: รีเซตวงเงินขึ้นปีใหม่อัตโนมัติ
    # ============================================================
    @api.model
    def _cron_rollover_annual_limit(self):
        """ต้นปีใหม่ — ก๊อปปี้วงเงินของปีก่อนหน้ามาตั้งเป็นวงเงินของปีปัจจุบัน

        ทำเฉพาะรายการที่ "ยังไม่มีของปีนี้" เท่านั้น ถ้า HR ตั้งวงเงินปีใหม่
        ไว้เองแล้วจะไม่ไปทับ รันซ้ำกี่รอบก็ได้ผลเหมือนเดิม
        """
        Limit = self.sudo()
        year = fields.Date.context_today(self).year
        prev_year = year - 1

        # ยกมาเฉพาะวงเงินที่ยังใช้งานอยู่ — ที่ถูก archive ไว้ถือว่าตั้งใจเลิกใช้
        prev_records = Limit.search([('year', '=', prev_year)])
        if not prev_records:
            _logger.info('Medical limit rollover: ไม่มีวงเงินปี %s ให้ยกมา — ข้าม', prev_year)
            return 0

        existing_keys = set(Limit.with_context(active_test=False).search(
            [('year', '=', year)]).mapped(lambda r: r.employee_id.id or False))

        created = 0
        for prev in prev_records:
            key = prev.employee_id.id or False
            if key in existing_keys:
                continue
            Limit.create({
                'year': year,
                'employee_id': key,
                'amount': prev.amount,
                'note': 'ยกวงเงินมาจากปี %s อัตโนมัติ' % prev_year,
            })
            existing_keys.add(key)
            created += 1

        _logger.info('Medical limit rollover: สร้างวงเงินปี %s ใหม่ %d รายการ', year, created)
        return created


class MedicalExpenseOpening(models.Model):
    """ยอดที่พนักงานเบิกไปแล้ว "ก่อน" เริ่มใช้ระบบนี้

    ก่อนมีระบบ พนักงานเบิกค่ารักษาพยาบาลผ่านกระดาษ Odoo จึงไม่รู้ว่าใครใช้ไปเท่าไหร่แล้ว
    ถ้าไม่บันทึกไว้ ทุกคนจะดูเหมือนยังมีวงเงินเต็มทั้งที่เบิกไปแล้วครึ่งหนึ่ง

    แยกเป็นคนละโมเดลกับ medical.expense.limit เพราะเป็นคนละเรื่อง:
      • limit   = "ปีนี้ให้เบิกได้เท่าไหร่" ตั้งครั้งเดียวใช้ทุกปี ยกข้ามปีได้
      • opening = "ปีนี้เบิกไปแล้วเท่าไหร่ก่อนเข้าระบบ" เป็นข้อมูลเฉพาะปี ห้ามยกข้ามปี
    ถ้ายัดรวมกันจะเผลอยกยอดเก่าข้ามปีไปหักซ้ำ และการมีแถวรายคนจะไปตรึงวงเงินคนนั้นไว้
    โดยไม่ได้ตั้งใจ
    """
    _name = 'medical.expense.opening'
    _description = 'ยอดค่ารักษาพยาบาลที่เบิกไปแล้วก่อนใช้ระบบ'
    _order = 'year desc, employee_id'
    _rec_name = 'employee_id'

    year = fields.Integer(
        string='ปี (ค.ศ.)',
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    employee_id = fields.Many2one('employee.salary', string='พนักงาน',
                                  required=True, ondelete='cascade', index=True)
    employee_code = fields.Char(related='employee_id.employee_code',
                                string='รหัสพนักงาน', store=True, readonly=True)
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา',
                                related='employee_id.branch_id', store=True, readonly=True)
    company = fields.Selection(related='employee_id.company', string='บริษัท (สังกัด)',
                               store=True, readonly=True)

    used_amount = fields.Float(
        string='เบิกไปแล้วก่อนใช้ระบบ (บาท)',
        required=True,
        help='ยอดที่เบิกไปแล้วในปีนี้ผ่านช่องทางเดิม\n'
             'ถ้ามีแต่ตัวเลข "คงเหลือ" ให้กรอก = วงเงินต่อปี − คงเหลือ',
    )

    annual_limit = fields.Float(string='วงเงินต่อปี (บาท)', compute='_compute_preview')
    remaining_preview = fields.Float(string='คงเหลือหลังหัก (บาท)', compute='_compute_preview',
                                     help='ใช้ตรวจทานกับตัวเลขที่ HR ถืออยู่ '
                                          'รวมใบที่อนุมัติในระบบแล้วด้วย')
    note = fields.Char(string='หมายเหตุ')

    @api.depends('employee_id', 'year', 'used_amount')
    def _compute_preview(self):
        Expense = self.env['medical.expense'].sudo()
        Limit = self.env['medical.expense.limit'].sudo()
        for rec in self:
            if not rec.employee_id or not rec.year:
                rec.annual_limit = 0.0
                rec.remaining_preview = 0.0
                continue
            limit = Limit.get_limit_for(rec.employee_id, rec.year)
            in_system = sum(Expense.search([
                ('employee_id', '=', rec.employee_id.id),
                ('expense_year', '=', rec.year),
                ('state', '=', 'อนุมัติ'),
            ]).mapped('amount'))
            rec.annual_limit = limit
            rec.remaining_preview = limit - rec.used_amount - in_system

    @api.constrains('used_amount')
    def _check_used_amount(self):
        for rec in self:
            if rec.used_amount < 0:
                raise ValidationError('ยอดที่เบิกไปแล้วต้องไม่ติดลบ')

    @api.constrains('year', 'employee_id')
    def _check_unique(self):
        for rec in self:
            if self.sudo().search([
                ('year', '=', rec.year),
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
            ], limit=1):
                raise ValidationError(
                    'บันทึกยอดเดิมของ %s ปี %s ไว้แล้ว — แก้ไขรายการเดิมแทนการสร้างใหม่\n'
                    'ถ้าสร้างซ้ำ ยอดจะถูกหักสองรอบ'
                    % (rec.employee_id.display_name, rec.year))

    @api.model
    def get_used_before(self, employee, year):
        """ยอดที่เบิกไปแล้วก่อนใช้ระบบของพนักงานคนนี้ในปีที่ระบุ"""
        if not employee:
            return 0.0
        rec = self.sudo().search([
            ('year', '=', year),
            ('employee_id', '=', employee.id),
        ], limit=1)
        return rec.used_amount if rec else 0.0
