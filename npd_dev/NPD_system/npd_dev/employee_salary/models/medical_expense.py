# -*- coding: utf-8 -*-
import base64
import json
import requests
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

from .thai_banks import THAI_BANKS, BANK_SELECTION, bank_short_name
from .medical_expense_limit import DEFAULT_ANNUAL_LIMIT

_logger = logging.getLogger(__name__)

BANK_CODES = {b['code'] for b in THAI_BANKS}

API_URL = "https://npdhrms.com/api/api_medical_expense.php"


class MedicalExpense(models.Model):
    _name = 'medical.expense'
    _description = 'ค่ารักษาพยาบาล'
    # mail.thread ทำให้มีกล่อง "เอกสารแนบ" ที่โชว์รูปตัวอย่างใบเสร็จได้
    # และมีที่บันทึกโน้ตระหว่างผู้อนุมัติกับฝ่ายบัญชี
    _inherit = ['mail.thread']
    _order = 'created_at desc'
    _rec_name = 'username'

    # วงเงินสำรอง ใช้เมื่อยังไม่เคยตั้งวงเงินในเมนู "วงเงินค่ารักษาพยาบาลต่อปี"
    MEDICAL_ANNUAL_LIMIT = DEFAULT_ANNUAL_LIMIT

    php_id = fields.Integer(string='PHP ID', readonly=True, index=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน', required=True)
    employee_code = fields.Char(related='employee_id.employee_code', string='รหัสพนักงาน', store=True, readonly=True)
    username = fields.Char(string='ชื่อ-นามสกุล', compute='_compute_employee_info', store=True, readonly=True)
    work_date = fields.Date(string='วันที่ทำงาน', default=fields.Date.context_today)
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา',
                                related='employee_id.branch_id', store=True, readonly=True)
    # สังกัดของพนักงาน — ตัวชี้ว่าใบเบิกนี้จะไปสร้างใบการรับที่ฐานข้อมูลไหน
    company = fields.Selection(related='employee_id.company', string='บริษัท (สังกัด)',
                               store=True, readonly=True)
    department = fields.Char(string='แผนก', compute='_compute_employee_info', store=True, readonly=True)
    position = fields.Char(string='ตำแหน่ง', compute='_compute_employee_info', store=True, readonly=True)
    amount = fields.Float(string='จำนวนเงิน (บาท)', required=True)

    # ---- บัญชีที่ให้โอนเงินค่ารักษาพยาบาลเข้า (กรอกมาจากแอป) ----
    bank_name = fields.Selection(BANK_SELECTION, string='ธนาคารที่โอนเข้า')
    bank_account_number = fields.Char(string='เลขบัญชีธนาคาร')
    bank_account_name = fields.Char(string='ชื่อบัญชี')

    user_note = fields.Text(string='หมายเหตุ',
                            help='สร้างอัตโนมัติจากจำนวนเงิน + บัญชีธนาคาร '
                                 '(พนักงานแก้ไขในแอปไม่ได้)')
    file_path = fields.Char(string='ไฟล์แนบ (URL จาก PHP)', readonly=True)
    file_paths = fields.Text(string='ไฟล์แนบทั้งหมด (JSON จาก PHP)', readonly=True)
    attachment_line_ids = fields.One2many(
        'medical.expense.file', 'expense_id',
        string='ไฟล์แนบจากแอป', readonly=True,
    )
    attachment_count = fields.Integer(string='จำนวนไฟล์แนบ',
                                      compute='_compute_attachment_count')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'medical_expense_ir_attachment_rel',
        'expense_id', 'attachment_id',
        string='ไฟล์แนบ',
    )
    state = fields.Selection([
        ('รออนุมัติ', 'รออนุมัติ'),
        ('อนุมัติ', 'อนุมัติ'),
        ('ไม่อนุมัติ', 'ไม่อนุมัติ'),
        ('ยกเลิก', 'ยกเลิก'),
    ], string='สถานะ', default='รออนุมัติ', readonly=True)
    reason = fields.Text(string='เหตุผลจากผู้อนุมัติ')
    created_at = fields.Datetime(string='วันที่ส่งคำขอ', default=fields.Datetime.now, readonly=True)
    approved_at = fields.Datetime(string='วันที่อนุมัติ', readonly=True)

    # ---- ใบการรับ (account.voucher) ที่สร้างไว้ใน DB ของบริษัทพนักงาน ----
    voucher_db = fields.Char(string='ฐานข้อมูลปลายทาง', readonly=True, copy=False)
    voucher_ref_id = fields.Integer(string='ID ใบการรับ', readonly=True, copy=False)
    voucher_number = fields.Char(string='เลขที่ใบการรับ', readonly=True, copy=False, index=True)
    voucher_partner = fields.Char(string='ผู้จำหน่ายในใบการรับ', readonly=True, copy=False)
    voucher_created_at = fields.Datetime(string='วันที่ส่งเข้าการรับ', readonly=True, copy=False)

    # ปีที่นับวงเงิน — อิงจากปีของ "วันที่ทำงาน" (เก็บไว้เพื่อใช้ค้นหา/จัดกลุ่ม)
    expense_year = fields.Integer(string='ปี', compute='_compute_expense_year',
                                  store=True, readonly=True)
    # วงเงินต่อปี (โชว์บนฟอร์ม)
    annual_limit = fields.Float(string='วงเงินต่อปี (บาท)',
                                compute='_compute_remaining_amount')
    # ยอดที่ "อนุมัติแล้ว" สะสมในปีนี้ของพนักงานคนนี้ (รวมยอดที่เบิกก่อนใช้ระบบ)
    annual_approved_amount = fields.Float(string='อนุมัติแล้วปีนี้ (บาท)',
                                          compute='_compute_remaining_amount')
    # ยอดที่เบิกผ่านช่องทางเดิมก่อนเริ่มใช้ระบบ — HR บันทึกไว้ที่เมนูยอดยกมา
    annual_opening_amount = fields.Float(string='เบิกก่อนใช้ระบบ (บาท)',
                                         compute='_compute_remaining_amount')
    # ยอดที่ยัง "รออนุมัติ" สะสมในปีนี้ (กันวงเงินไว้ล่วงหน้า)
    annual_pending_amount = fields.Float(string='รออนุมัติปีนี้ (บาท)',
                                         compute='_compute_remaining_amount')
    # จำนวนเงินคงเหลือที่ขอได้ (นับเฉพาะสถานะอนุมัติ) — แสดงคงเหลือล่าสุด
    remaining_amount = fields.Float(string='จำนวนเงินคงเหลือที่ขอได้ (บาท)',
                                    compute='_compute_remaining_amount')

    @api.depends('work_date')
    def _compute_expense_year(self):
        for rec in self:
            d = rec.work_date or fields.Date.context_today(rec)
            rec.expense_year = d.year

    @api.depends('employee_id', 'expense_year', 'state', 'amount')
    def _compute_remaining_amount(self):
        """คงเหลือล่าสุด = วงเงินต่อปี − ผลรวมยอดที่ 'อนุมัติแล้ว' ทั้งหมดของพนักงานคนนี้
        ในปีเดียวกัน (นับเฉพาะ state = 'อนุมัติ' เท่านั้น — ไม่อนุมัติ/ยกเลิก ไม่นับ)

        วงเงินต่อปีดึงจากเมนู "วงเงินค่ารักษาพยาบาลต่อปี" (medical.expense.limit)
        แยกตามปี → ขึ้นปีใหม่ยอดใช้ไปเริ่มนับ 0 ใหม่เองอัตโนมัติ

        แสดงยอดคงเหลือ "ปัจจุบันจริง" ทุกใบของพนักงาน/ปีเดียวกันจะเห็นค่าเท่ากัน
        → พออนุมัติเพิ่ม คงเหลือจะลดลงตามทันที
        """
        # แคชต่อการคำนวณ 1 รอบ — ไม่งั้น tree 100 แถวจะยิง query หลายร้อยครั้ง
        limit_cache = {}
        usage_cache = {}
        opening_cache = {}
        for rec in self:
            year = rec.expense_year or fields.Date.context_today(rec).year
            key = (rec.employee_id.id or 0, year)

            if key not in limit_cache:
                limit_cache[key] = rec._get_annual_limit(rec.employee_id, year)
            limit = limit_cache[key]
            rec.annual_limit = limit

            if not rec.employee_id:
                rec.annual_approved_amount = 0.0
                rec.annual_pending_amount = 0.0
                rec.annual_opening_amount = 0.0
                rec.remaining_amount = limit
                continue

            if key not in usage_cache:
                usage_cache[key] = rec._get_year_usage(rec.employee_id, year)
            used, pending = usage_cache[key]

            if key not in opening_cache:
                opening_cache[key] = rec._get_opening_used(rec.employee_id, year)
            rec.annual_opening_amount = opening_cache[key]

            rec.annual_approved_amount = used
            rec.annual_pending_amount = pending
            rec.remaining_amount = limit - used

    @api.depends('attachment_line_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_line_ids)

    # ============================================================
    # ตัวช่วยเรื่องวงเงิน — ใช้ร่วมกันทั้งฟอร์ม, ปุ่มอนุมัติ และ API ของแอป
    # ============================================================
    @api.model
    def _get_annual_limit(self, employee, year):
        """วงเงินค่ารักษาพยาบาลต่อปีของพนักงานคนนี้ (บาท)"""
        return self.env['medical.expense.limit'].sudo().get_limit_for(employee, year)

    @api.model
    def _get_year_usage(self, employee, year):
        """คืน (ยอดอนุมัติแล้ว, ยอดรออนุมัติ) ของพนักงานคนนี้ในปีที่ระบุ

        "ยอดอนุมัติแล้ว" รวมยอดที่เบิกไปก่อนเริ่มใช้ระบบด้วย (medical.expense.opening)
        ไม่งั้นคนที่เบิกผ่านกระดาษไปแล้วครึ่งวงเงินจะดูเหมือนยังมีวงเงินเต็ม
        """
        if not employee:
            return 0.0, 0.0
        records = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('expense_year', '=', year),
            ('state', 'in', ['อนุมัติ', 'รออนุมัติ']),
        ])
        approved = sum(r.amount for r in records if r.state == 'อนุมัติ')
        pending = sum(r.amount for r in records if r.state == 'รออนุมัติ')
        approved += self._get_opening_used(employee, year)
        return approved, pending

    @api.model
    def _get_opening_used(self, employee, year):
        """ยอดที่เบิกไปแล้วก่อนใช้ระบบ (บันทึกโดย HR)"""
        return self.env['medical.expense.opening'].sudo().get_used_before(employee, year)

    @api.constrains('php_id')
    def _check_unique_php_id(self):
        for rec in self:
            if rec.php_id:
                duplicate = self.sudo().search([
                    ('php_id', '=', rec.php_id),
                    ('id', '!=', rec.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError("ข้อมูลนี้มีอยู่แล้วในระบบ (PHP ID ซ้ำ)")

    # ============================================================
    # Auto-fill ข้อมูลจาก employee.salary เมื่อเลือกพนักงาน
    # ============================================================
    @api.depends('employee_id')
    def _compute_employee_info(self):
        for rec in self:
            emp = rec.employee_id
            if emp:
                rec.username = ' '.join(filter(None, [
                    emp.prefix_th or '',
                    emp.firstname or '',
                    emp.lastname or '',
                ])).strip()
                rec.department = emp.department_id.name if emp.department_id else ''
                rec.position = emp.position_id.name if emp.position_id else ''
            else:
                rec.username = ''
                rec.department = ''
                rec.position = ''

    # ============================================================
    # หมายเหตุอัตโนมัติ — สร้างจากจำนวนเงิน + บัญชีธนาคารที่พนักงานเลือก
    # แอปโชว์ข้อความชุดนี้แบบแก้ไขไม่ได้ ฝั่ง Odoo จึงสร้างซ้ำให้ตรงกัน
    # ============================================================
    def _build_auto_note(self):
        self.ensure_one()
        lines = ['ค่ารักษาพยาบาล {:,.2f} บาท'.format(self.amount or 0.0)]
        second = []
        short = bank_short_name(self.bank_name)
        if short:
            second.append(short)
        if self.bank_account_number:
            second.append('เลขบัญชี %s' % self.bank_account_number)
        if self.bank_account_name:
            second.append(self.bank_account_name)
        if second:
            lines.append(' '.join(second))
        return chr(10).join(lines)

    def _refresh_auto_note(self):
        """เขียนหมายเหตุอัตโนมัติทับ เฉพาะใบที่มีข้อมูลบัญชีครบ

        ใบเก่าที่ยังไม่มีบัญชีธนาคาร (ก่อนเพิ่มฟีเจอร์นี้) จะไม่ถูกแตะ
        """
        for rec in self:
            if not rec.bank_name or not rec.bank_account_number:
                continue
            note = rec._build_auto_note()
            if rec.user_note != note:
                rec.with_context(skip_medical_note=True).sudo().write({'user_note': note})

    @api.model_create_multi
    def create(self, vals_list):
        records = super(MedicalExpense, self).create(vals_list)
        records._refresh_auto_note()
        return records

    def write(self, vals):
        res = super(MedicalExpense, self).write(vals)
        if not self.env.context.get('skip_medical_note'):
            triggers = {'amount', 'bank_name', 'bank_account_number', 'bank_account_name'}
            if triggers.intersection(vals.keys()):
                self._refresh_auto_note()
        return res

    # ============================================================
    # ไฟล์แนบหลายไฟล์จากแอป
    # ============================================================
    @api.model
    def _parse_file_paths(self, raw, fallback=''):
        """แปลงค่า file_paths ที่ PHP ส่งมา (JSON list / string) เป็น list ของ path"""
        paths = []
        if raw:
            if isinstance(raw, (list, tuple)):
                paths = [str(x) for x in raw]
            else:
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        paths = [str(x) for x in data]
                    elif isinstance(data, str) and data:
                        paths = [data]
                except (TypeError, ValueError):
                    paths = str(raw).split(',')
        if not paths and fallback:
            paths = [fallback]

        seen, cleaned = set(), []
        for path in paths:
            path = (path or '').strip()
            if path and path not in seen:
                seen.add(path)
                cleaned.append(path)
        return cleaned

    def _sync_attachment_lines(self, paths):
        """ทำให้รายการไฟล์แนบใน Odoo ตรงกับที่แอปส่งมา (ลบของเก่า สร้างใหม่)"""
        self.ensure_one()
        paths = list(paths or [])
        if self.attachment_line_ids.mapped('file_path') != paths:
            self.attachment_line_ids.sudo().unlink()
            MedicalFile = self.env['medical.expense.file'].sudo()
            for index, path in enumerate(paths, start=1):
                MedicalFile.create({
                    'expense_id': self.id,
                    'sequence': index,
                    'name': path.split('/')[-1],
                    'file_path': path,
                })
        self._download_app_attachments()

    def _download_app_attachments(self):
        """โหลดไฟล์จากเซิร์ฟเวอร์ PHP มาเก็บเป็นเอกสารแนบของคำขอนี้

        ทำให้เห็นรูปตัวอย่างใบเสร็จในกล่องเอกสารแนบได้ทันที ไม่ต้องกดเปิดทีละไฟล์
        และยังเปิดดูย้อนหลังได้แม้เซิร์ฟเวอร์ PHP จะล่มหรือไฟล์ถูกลบไปแล้ว

        โหลดเฉพาะไฟล์ที่ยังไม่เคยเก็บ — กดซิงค์ซ้ำกี่รอบก็ไม่โหลดซ้ำ
        """
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        already = set(Attachment.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ]).mapped('name'))

        for line in self.attachment_line_ids:
            name = (line.name or '').strip()
            url = line._build_url()
            if not name or not url or name in already:
                continue
            try:
                response = requests.get(url, timeout=60)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                # ไฟล์โหลดไม่ได้ไม่ควรทำให้การซิงค์ทั้งชุดล้ม
                _logger.warning('โหลดไฟล์แนบ %s ไม่สำเร็จ: %s', url, e)
                continue
            Attachment.create({
                'name': name,
                'datas': base64.b64encode(response.content),
                'res_model': self._name,
                'res_id': self.id,
            })
            already.add(name)

    # ============================================================
    # API สำหรับแอป (JSON-RPC): วงเงินคงเหลือ + รายชื่อธนาคาร
    #   callKw('medical.expense', 'api_get_medical_info', [employee_code])
    # ============================================================
    @api.model
    def api_get_medical_info(self, employee_code, exclude_php_id=None, year=None):
        """ข้อมูลที่แอปต้องใช้ตอนกรอกคำขอค่ารักษาพยาบาล

        remaining = วงเงินต่อปี − อนุมัติแล้ว − รออนุมัติ
        (กันยอดที่ยื่นค้างไว้ ไม่ให้ยื่นซ้ำจนเกินวงเงิน)

        exclude_php_id: id ของคำขอที่กำลังแก้ไขอยู่ — ไม่ต้องเอายอดตัวเองมาหักซ้ำ
        """
        banks = [dict(b) for b in THAI_BANKS]
        target_year = int(year) if year else fields.Date.context_today(self).year

        employee = False
        if employee_code:
            employee = self.env['employee.salary'].sudo().search(
                [('employee_code', '=', employee_code)], limit=1)

        if not employee:
            return {
                'ok': False,
                'message': 'ไม่พบข้อมูลพนักงานรหัส %s ในระบบ' % (employee_code or '-'),
                'year': target_year,
                'banks': banks,
            }

        limit = self._get_annual_limit(employee, target_year)
        approved, pending = self._get_year_usage(employee, target_year)

        # ถ้ากำลังแก้ไขคำขอเดิม ยอดของใบนั้นไม่ควรถูกหักซ้ำ
        if exclude_php_id:
            own = self.sudo().search([
                ('php_id', '=', int(exclude_php_id)),
                ('expense_year', '=', target_year),
                ('employee_id', '=', employee.id),
            ], limit=1)
            if own:
                if own.state == 'อนุมัติ':
                    approved -= own.amount
                elif own.state == 'รออนุมัติ':
                    pending -= own.amount

        remaining = limit - approved - pending
        full_name = ' '.join(filter(None, [
            employee.prefix_th or '',
            employee.firstname or '',
            employee.lastname or '',
        ])).strip()

        return {
            'ok': True,
            'year': target_year,
            'employee_name': full_name,
            'limit': float(limit),
            'used_approved': float(approved),
            'used_pending': float(pending),
            'remaining': float(max(remaining, 0.0)),
            'bank_name': employee.bank_name or '',
            'bank_account_number': employee.bank_account_number or '',
            'banks': banks,
        }

    # ============================================================
    # อนุมัติ — พร้อมสร้างใบการรับใน DB ของบริษัทพนักงาน
    # ============================================================
    def action_approve(self):
        for rec in self:
            if rec.state != 'รออนุมัติ':
                raise UserError("สามารถอนุมัติได้เฉพาะคำขอที่สถานะ 'รออนุมัติ' เท่านั้น")

            # ✅ เช็ควงเงินค่ารักษาพยาบาลต่อปี — อนุมัติไม่ได้ถ้าเกินวงเงินคงเหลือ
            #    นับเฉพาะใบที่ 'อนุมัติ' แล้วในปีเดียวกันของพนักงานคนนี้
            #    วงเงินมาจากเมนู "วงเงินค่ารักษาพยาบาลต่อปี" แยกตามปี
            year = rec.expense_year or fields.Date.context_today(rec).year
            limit = rec._get_annual_limit(rec.employee_id, year)
            used, _pending = rec._get_year_usage(rec.employee_id, year)
            remaining = limit - used
            if rec.amount > remaining:
                raise UserError(
                    f"ไม่สามารถอนุมัติได้ — เกินวงเงินค่ารักษาพยาบาลประจำปี {year}\n\n"
                    f"• วงเงินต่อปี: {limit:,.2f} บาท\n"
                    f"• อนุมัติไปแล้วปีนี้: {used:,.2f} บาท\n"
                    f"• คงเหลือที่ขอได้: {remaining:,.2f} บาท\n"
                    f"• คำขอนี้: {rec.amount:,.2f} บาท"
                )

            # หา config ปลายทางก่อนทำอะไรทั้งสิ้น — ถ้ายังไม่ได้ตั้งค่า
            # ต้องหยุดตั้งแต่ยังไม่แตะสถานะที่ไหนเลย
            cfg = self.env['medical.expense.voucher.config'].sudo().get_for_employee(
                rec.employee_id)

            # ลำดับนี้สำคัญ: push สถานะไป PHP ก่อน แล้วค่อยสร้างใบการรับ
            # ถ้าสลับกันแล้วขั้น PHP ล้ม จะเหลือ "ใบการรับที่ไม่ควรมี" ค้างในบัญชี
            # ซึ่งลบไม่ได้ ส่วนทางนี้ถ้าล้มแค่กดอนุมัติซ้ำก็หายเอง
            rec._sync_state_to_php('approve')
            result = cfg.create_voucher_for_expense(rec)

            rec.sudo().write({
                'state': 'อนุมัติ',
                'approved_at': fields.Datetime.now(),
                'reason': '',
                'voucher_db': result.get('db'),
                'voucher_ref_id': result.get('voucher_id'),
                'voucher_number': result.get('number'),
                'voucher_partner': result.get('partner'),
                'voucher_created_at': fields.Datetime.now(),
            })

    # ============================================================
    # ถอยกลับการอนุมัติ — ยกเลิกใบการรับ แล้วคืนวงเงิน
    # ============================================================
    def _cancel_linked_voucher(self):
        """ยกเลิกใบการรับที่ผูกกับคำขอนี้ (ถ้ามี)

        ใช้ร่วมกันทั้งปุ่ม "ถอยกลับการอนุมัติ" และ "ยกเลิก" — ทั้งสองทางต้อง
        ปิดเอกสารฝั่งบัญชีให้ด้วย ไม่งั้นจะเหลือใบจ่ายเงินค้างที่ไม่มีคำขอรองรับ
        """
        self.ensure_one()
        if not self.voucher_ref_id:
            return False
        Config = self.env['medical.expense.voucher.config'].sudo()
        cfg = Config.search([('db_name', '=', self.voucher_db)], limit=1)
        if not cfg:
            cfg = Config.get_for_employee(self.employee_id)
        return cfg.cancel_voucher(self.voucher_ref_id)

    def action_revert_approval(self):
        for rec in self:
            if rec.state != 'อนุมัติ':
                raise UserError("ถอยกลับได้เฉพาะคำขอที่อนุมัติไปแล้วเท่านั้น")

            # ลำดับเดียวกับตอนอนุมัติ — PHP ก่อน แล้วค่อยแตะเอกสารบัญชี
            rec._sync_state_to_php('pending')
            rec._cancel_linked_voucher()

            # เคลียร์เลขใบเดิมทิ้ง กดอนุมัติใหม่จะได้สร้างใบใหม่ ไม่ไปใช้ใบที่ยกเลิกแล้ว
            rec.sudo().write({
                'state': 'รออนุมัติ',
                'approved_at': False,
                'reason': '',
                'voucher_db': False,
                'voucher_ref_id': 0,
                'voucher_number': False,
                'voucher_partner': False,
                'voucher_created_at': False,
            })

    # ============================================================
    # เปิดใบการรับใน DB ปลายทาง (คนละฐานข้อมูล ต้องสลับ db ที่ URL)
    # ============================================================
    def action_open_voucher(self):
        self.ensure_one()
        if not (self.voucher_db and self.voucher_ref_id):
            raise UserError('คำขอนี้ยังไม่มีใบการรับ')
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'https://npderp.com')
        return {
            'type': 'ir.actions.act_url',
            'url': '%s/web?db=%s#id=%s&model=account.voucher&view_type=form' % (
                base_url.rstrip('/'), self.voucher_db, self.voucher_ref_id),
            'target': 'new',
        }

    # ============================================================
    # ไม่อนุมัติ — เปิด popup ถามเหตุผล
    # ============================================================
    def action_reject(self):
        self.ensure_one()
        if self.state != 'รออนุมัติ':
            raise UserError("สามารถไม่อนุมัติได้เฉพาะคำขอที่สถานะ 'รออนุมัติ' เท่านั้น")
        return {
            'type': 'ir.actions.act_window',
            'name': 'ไม่อนุมัติค่ารักษาพยาบาล',
            'res_model': 'medical.expense.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_expense_id': self.id},
        }

    # ============================================================
    # ยกเลิก
    # ============================================================
    def action_cancel(self):
        for rec in self:
            rec._sync_state_to_php('cancel')
            # ยกเลิกใบการรับฝั่งบัญชีด้วย ถ้าคำขอนี้เคยอนุมัติไปแล้ว
            rec._cancel_linked_voucher()
            rec.sudo().write({
                'state': 'ยกเลิก',
                'approved_at': fields.Datetime.now(),
            })

    # ============================================================
    # เปิดไฟล์แนบ (URL จาก PHP เดิม)
    # ============================================================
    def action_open_attachment(self):
        self.ensure_one()
        if not self.file_path:
            raise UserError("ไม่มีไฟล์แนบ")

        base_url = 'https://npdhrms.com/api/'
        file_url = self.file_path
        if not file_url.startswith('http'):
            file_url = base_url + file_url

        return {
            'type': 'ir.actions.act_url',
            'url': file_url,
            'target': 'new',
        }

    # ============================================================
    # เปิดหน้าตั้งวงเงินค่ารักษาพยาบาลของปีนี้
    # ============================================================
    def action_open_annual_limit(self):
        self.ensure_one()
        year = self.expense_year or fields.Date.context_today(self).year
        return {
            'type': 'ir.actions.act_window',
            'name': 'วงเงินค่ารักษาพยาบาลต่อปี %s' % year,
            'res_model': 'medical.expense.limit',
            'view_mode': 'tree,form',
            'domain': [('year', '=', year)],
            'context': {'default_year': year},
            'target': 'current',
        }

    # ============================================================
    # Sync ดึงรายการค่ารักษาพยาบาลทั้งหมดจาก PHP API
    # ============================================================
    @api.model
    def sync_from_api(self):
        """ดึงคำขอค่ารักษาพยาบาลจากแอป (PHP) มาเก็บใน Odoo
        - record ที่มีอยู่แล้ว (php_id ตรงกัน) จะอัปเดตเฉพาะข้อมูลที่ผู้ใช้แอปแก้ไข
          ยกเว้น state ที่อนุมัติแล้วใน Odoo จะไม่ทับ
        - record ใหม่จะสร้างขึ้น โดยจับคู่ employee_id จาก employee_code
        """
        _logger.info("Medical Expense sync_from_api: starting...")
        try:
            response = requests.get(API_URL, timeout=30)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException as e:
            raise UserError("ไม่สามารถเชื่อมต่อ PHP API ได้: %s" % e)

        if result.get('status') != 'success':
            raise UserError("API Error: %s" % result.get('message', 'Unknown'))

        records = result.get('data') or []
        if not records:
            _logger.info("Medical Expense sync_from_api: no records from API.")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'ซิงค์ข้อมูลค่ารักษาพยาบาล',
                    'message': 'ไม่พบรายการใหม่จาก PHP',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        Emp = self.env['employee.salary'].sudo()
        created = 0
        updated = 0
        for rec in records:
            php_id = int(rec.get('id') or 0)
            if php_id <= 0:
                continue

            # หา employee.salary
            # ลำดับ: 1) firstname + lastname จาก username (ชื่อจาก API ถูกต้องกว่า code)
            #        2) fallback ด้วย employee_code ถ้าไม่เจอชื่อ
            employee = False
            username = (rec.get('username') or '').strip()
            emp_code = (rec.get('employee_code') or '').strip()

            # 1. ลองจับด้วยชื่อ (split by any whitespace)
            if username:
                parts = username.split(None, 1)
                if len(parts) == 2:
                    employee = Emp.search([
                        ('firstname', '=', parts[0].strip()),
                        ('lastname', '=', parts[1].strip()),
                    ], limit=1)
                if not employee:
                    # ลอง firstname อย่างเดียว (กรณีชื่อไม่มีนามสกุล)
                    employee = Emp.search([('firstname', '=', username)], limit=1)

            # 2. fallback ด้วย employee_code ถ้ายังไม่เจอ
            if not employee and emp_code:
                employee = Emp.search([('employee_code', '=', emp_code)], limit=1)

            work_date = rec.get('work_date')
            try:
                amount = float(rec.get('amount') or 0)
            except (TypeError, ValueError):
                amount = 0.0

            state = (rec.get('state') or 'รออนุมัติ').strip()
            user_note = rec.get('user_note') or ''
            reason = rec.get('reason') or ''
            file_path = rec.get('file_path') or ''
            approved_at = rec.get('approved_at')

            # บัญชีที่ให้โอนเข้า (พนักงานเลือกมาจากแอป)
            bank_code = (rec.get('bank_name') or '').strip().upper()
            if bank_code not in BANK_CODES:
                bank_code = False
            bank_account_number = (rec.get('bank_account_number') or '').strip()
            bank_account_name = (rec.get('bank_account_name') or '').strip()

            # ไฟล์แนบ — แอปแนบได้หลายไฟล์ PHP ส่งมาเป็น JSON list ใน file_paths
            paths = self._parse_file_paths(rec.get('file_paths'), file_path)

            vals = {
                'php_id': php_id,
                'work_date': work_date or fields.Date.context_today(self),
                'amount': amount,
                'user_note': user_note,
                'reason': reason,
                'file_path': paths[0] if paths else file_path,
                'file_paths': json.dumps(paths, ensure_ascii=False) if paths else False,
                'bank_name': bank_code,
                'bank_account_number': bank_account_number,
                'bank_account_name': bank_account_name,
            }
            if employee:
                vals['employee_id'] = employee.id
                # ชื่อบัญชียึดทะเบียนพนักงานเป็นหลักเสมอ ไม่ใช่ชื่อที่แอปส่งมา
                # แอปบางเครื่องยังไม่มีคำนำหน้า/นามสกุลครบ (ติดต่อ Odoo ไม่ได้ตอนกรอก)
                # ปล่อยไว้ฝ่ายบัญชีจะโอนผิดชื่อ
                master_name = ' '.join(filter(None, [
                    employee.prefix_th or '',
                    employee.firstname or '',
                    employee.lastname or '',
                ])).strip()
                if master_name:
                    vals['bank_account_name'] = master_name
            if approved_at and approved_at != '0000-00-00 00:00:00':
                vals['approved_at'] = approved_at

            existing = self.sudo().search([('php_id', '=', php_id)], limit=1)
            if existing:
                # ถ้าใน Odoo อนุมัติ/ไม่อนุมัติ/ยกเลิกไปแล้ว — ไม่ทับ state
                # อัปเดตเฉพาะเนื้อหา (work_date, amount, user_note, ไฟล์แนบ, บัญชีธนาคาร)
                #
                # รับจาก PHP ได้เฉพาะ "ยกเลิก" เท่านั้น (พนักงานกดยกเลิกเองในแอป)
                # การอนุมัติเป็นสิทธิ์ของ Odoo ฝ่ายเดียว เพราะผูกกับการสร้างใบการรับ
                # ถ้าปล่อยให้ PHP ดันสถานะเป็น 'อนุมัติ' ได้ จะเกิดใบที่อนุมัติแล้ว
                # แต่ไม่มีเอกสารบัญชีรองรับ
                if existing.state == 'รออนุมัติ' and state == 'ยกเลิก':
                    vals['state'] = state
                existing.sudo().write(vals)
                existing._sync_attachment_lines(paths)
                updated += 1
            else:
                vals['state'] = state
                new_rec = self.sudo().create(vals)
                new_rec._sync_attachment_lines(paths)
                created += 1

        _logger.info("Medical Expense sync_from_api: created=%d updated=%d", created, updated)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ซิงค์ข้อมูลค่ารักษาพยาบาล',
                'message': 'เพิ่มใหม่ %d รายการ / อัปเดต %d รายการ' % (created, updated),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def sync_and_open_view(self):
        """sync + เปิดหน้า tree view"""
        self.sync_from_api()
        return {
            'type': 'ir.actions.act_window',
            'name': 'ค่ารักษาพยาบาล',
            'res_model': 'medical.expense',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    # ============================================================
    # Sync state กลับไป PHP — เฉพาะ record ที่มาจาก PHP เท่านั้น
    # ============================================================
    def _sync_state_to_php(self, action, reason=''):
        self.ensure_one()
        if not self.php_id:
            return
        try:
            payload = {
                'request_id': self.php_id,
                'action': action,
                'reason': reason or '',
            }
            _logger.info("Medical Expense sync to PHP: %s", payload)

            response = requests.post(API_URL, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get('status') != 'success':
                raise UserError("API Error: %s" % result.get('message', 'Unknown error'))

        except requests.exceptions.RequestException as e:
            _logger.error("Failed to sync medical expense to PHP (ID=%s): %s", self.php_id, e)
            raise UserError("ไม่สามารถอัพเดทสถานะไป PHP ได้: %s" % e)

    # ============================================================
    # ห้ามลบรายการที่อนุมัติแล้ว
    # ============================================================
    def unlink(self):
        for rec in self:
            if rec.state == 'อนุมัติ':
                raise UserError(
                    "ไม่สามารถลบรายการค่ารักษาพยาบาลของ %s ได้ "
                    "เนื่องจากอนุมัติแล้ว" % (rec.username or rec.employee_code or ''))
        return super(MedicalExpense, self).unlink()


class MedicalExpenseFile(models.Model):
    """ไฟล์แนบ 1 ไฟล์ที่พนักงานแนบมากับคำขอค่ารักษาพยาบาลจากแอป

    ไฟล์จริงเก็บอยู่บนเซิร์ฟเวอร์ PHP (npdhrms.com) ที่นี่เก็บแค่ path
    เพื่อทำลิงก์เปิดดู — คำขอค่ารักษาพยาบาลแนบได้มากกว่า 1 ไฟล์
    """
    _name = 'medical.expense.file'
    _description = 'ไฟล์แนบค่ารักษาพยาบาล (จากแอป)'
    _order = 'sequence, id'

    expense_id = fields.Many2one('medical.expense', string='คำขอค่ารักษาพยาบาล',
                                 required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='ลำดับ', default=1)
    name = fields.Char(string='ชื่อไฟล์')
    file_path = fields.Char(string='ที่อยู่ไฟล์', required=True)
    file_url = fields.Char(string='ลิงก์', compute='_compute_file_url')

    @api.depends('file_path')
    def _compute_file_url(self):
        for rec in self:
            rec.file_url = rec._build_url()

    def _build_url(self):
        self.ensure_one()
        path = (self.file_path or '').strip().replace(chr(92), '/')
        if not path:
            return ''
        if path.startswith('http://') or path.startswith('https://'):
            return path
        while path.startswith('../') or path.startswith('./'):
            path = path[3:] if path.startswith('../') else path[2:]
        path = path.lstrip('/')
        if path.startswith('api/'):
            path = path[4:]
        return 'https://npdhrms.com/api/' + path

    def action_open(self):
        self.ensure_one()
        url = self._build_url()
        if not url:
            raise UserError('ไม่พบที่อยู่ไฟล์แนบ')
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }


class MedicalExpenseRejectWizard(models.TransientModel):
    _name = 'medical.expense.reject.wizard'
    _description = 'Wizard ไม่อนุมัติค่ารักษาพยาบาล'

    expense_id = fields.Many2one('medical.expense', string='คำขอ', required=True)
    reason = fields.Text(string='เหตุผลในการไม่อนุมัติ', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason:
            raise UserError("กรุณากรอกเหตุผล")
        expense = self.expense_id
        expense._sync_state_to_php('reject', reason=self.reason)
        expense.sudo().write({
            'state': 'ไม่อนุมัติ',
            'reason': self.reason,
            'approved_at': fields.Datetime.now(),
        })
