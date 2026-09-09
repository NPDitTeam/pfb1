# -*- coding: utf-8 -*-
"""ส่งค่ารักษาพยาบาลที่อนุมัติแล้ว ไปสร้างใบ "การรับ" (account.voucher) ใน DB ของบริษัทพนักงาน

ทำไมไม่ใช้ SQL ตรง ๆ ทั้งที่อยู่เซิร์ฟเวอร์เดียวกัน
--------------------------------------------------
การ post ใบการรับ (`proforma_voucher` → `action_move_line_create`) ไม่ได้แค่เขียน
1 แถวลง `account_voucher` แต่ยังสร้าง `account_move` + `account_move_line` ทั้งชุด
ดึงเลขจาก `ir.sequence` และไล่ผูกกับบัญชี/สาขา/ภาษี ถ้าเขียนด้วย INSERT เอง
งบการเงินของบริษัทนั้นจะเพี้ยนแบบที่ตรวจไม่เจอจนกว่าจะปิดงบ

ที่นี่จึงเปิด registry ของ DB ปลายทางในโปรเซสเดียวกัน แล้วเรียก ORM ตามปกติ
ได้ business logic ครบเหมือนคนกดเองในหน้าจอ แต่ยังเป็น cross-DB อยู่

ทุก DB มีข้อมูลอ้างอิงคนละ id (สมุดรายวัน/วิธีจ่าย/สินค้า/ผังบัญชี) จึงต้อง
ตั้งค่าแมปไว้ที่ medical.expense.voucher.config ก่อนใช้งาน
"""
import base64
import logging
from contextlib import contextmanager

import requests

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.modules.registry import Registry
from odoo import SUPERUSER_ID

from .employee_salary import EmployeeSalary

_logger = logging.getLogger(__name__)

PHP_BASE_URL = 'https://npdhrms.com/api/'


class MedicalExpenseVoucherConfig(models.Model):
    _name = 'medical.expense.voucher.config'
    _description = 'ตั้งค่าส่งค่ารักษาพยาบาลเข้าหน้าการรับ'
    _order = 'company'
    _rec_name = 'company'

    company = fields.Selection(
        selection=EmployeeSalary.HRMS_COMPANY,
        string='บริษัท (สังกัดพนักงาน)',
        required=True,
        help='อิงจากฟิลด์ "บริษัท" ในทะเบียนพนักงาน',
    )
    db_name = fields.Char(string='ชื่อฐานข้อมูลปลายทาง', required=True,
                          help='เช่น NPD_S_Group_New_V2')
    active = fields.Boolean(string='ใช้งาน', default=True)

    # ---- id ของข้อมูลอ้างอิงใน DB ปลายทาง (แต่ละ DB ไม่เหมือนกัน) ----
    target_company_id = fields.Integer(string='res.company id', required=True, default=1)
    target_journal_id = fields.Integer(string='สมุดรายวัน (journal) id', required=True,
                                       help='สมุดรายวันจ่ายชำระ เช่น PVV')
    target_payment_journal_id = fields.Integer(string='สมุดรายวันจ่ายชำระ (payment journal) id')
    target_payment_method_id = fields.Integer(string='Payment Method id', required=True,
                                              help='เช่น เงินโอนธนาคาร KBANK 777-4')
    target_product_id = fields.Integer(string='สินค้า (product) id',
                                       help='เว้นว่างได้ ถ้าไม่ใช้สินค้าในบรรทัดบิล')
    target_account_id = fields.Integer(string='บัญชี (account) id', required=True,
                                       help='เช่น 5200-24 ค่ารักษาพยาบาล')
    target_analytic_id = fields.Integer(
        string='บัญชีวิเคราะห์ (analytic) id',
        help='ใบเบิกค่ารักษาพยาบาลจะลงบัญชีวิเคราะห์นี้เสมอ ไม่แปรตามสาขาของพนักงาน '
             '(ปกติตั้งเป็นสำนักงานใหญ่ เพราะเป็นสวัสดิการระดับบริษัท)')
    target_default_branch_id = fields.Integer(string='สาขาเริ่มต้น (res.branch) id', required=True,
                                              help='ใช้เมื่อจับคู่สาขาของพนักงานไม่ได้')

    line_label = fields.Char(string='ชื่อรายการในบิล', required=True,
                             default='ค่ารักษาพยาบาล-พนง.ขาย')
    reference_text = fields.Char(string='Bill Reference', required=True,
                                 default='เบิกค่ารักษาพยาบาล')

    note = fields.Char(string='หมายเหตุ')

    _sql_constraints = [
        ('company_uniq', 'unique(company)', 'ตั้งค่าบริษัทนี้ไว้แล้ว — แก้ไขรายการเดิมแทน'),
    ]

    @api.constrains('db_name')
    def _check_db_name(self):
        for rec in self:
            if not (rec.db_name or '').strip():
                raise ValidationError('กรุณากรอกชื่อฐานข้อมูลปลายทาง')

    # ============================================================
    # เปิด environment ของ DB ปลายทาง
    # ============================================================
    @contextmanager
    def _target_env(self):
        """เปิด cursor ของ DB ปลายทาง — commit เมื่อจบโดยไม่มี exception

        transaction แยกจาก DB ปัจจุบัน ถ้าฝั่ง HRMS rollback ทีหลัง
        ใบที่สร้างไปแล้วจะไม่ถูกลบตาม จึงต้องบันทึกเลขใบกลับมาทันที
        และให้ทุกขั้นตอนเช็คซ้ำได้ว่าเคยสร้างไปหรือยัง
        """
        self.ensure_one()
        db_name = (self.db_name or '').strip()
        try:
            registry = Registry(db_name)
        except Exception as e:
            raise UserError('เปิดฐานข้อมูล "%s" ไม่ได้: %s' % (db_name, e))

        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            yield env

    # ============================================================
    # ปุ่มทดสอบ — เช็คว่า id ที่ตั้งไว้มีอยู่จริงทุกตัว
    # ============================================================
    def action_test_connection(self):
        self.ensure_one()
        problems = []
        with self._target_env() as env:
            checks = [
                ('res.company', self.target_company_id, 'บริษัท'),
                ('account.journal', self.target_journal_id, 'สมุดรายวัน'),
                ('payment.method', self.target_payment_method_id, 'Payment Method'),
                ('account.account', self.target_account_id, 'บัญชี'),
                ('res.branch', self.target_default_branch_id, 'สาขาเริ่มต้น'),
            ]
            if self.target_payment_journal_id:
                checks.append(('account.journal', self.target_payment_journal_id,
                               'สมุดรายวันจ่ายชำระ'))
            if self.target_product_id:
                checks.append(('product.product', self.target_product_id, 'สินค้า'))
            if self.target_analytic_id:
                checks.append(('account.analytic.account', self.target_analytic_id,
                               'บัญชีวิเคราะห์'))

            for model, res_id, label in checks:
                if model not in env:
                    problems.append('ไม่มีโมเดล %s ใน DB นี้' % model)
                    continue
                rec = env[model].browse(res_id).exists()
                if not rec:
                    problems.append('%s id=%s ไม่มีอยู่จริง' % (label, res_id))
                else:
                    problems.append('OK — %s: %s' % (label, rec.display_name))

        message = '\n'.join(problems)
        raise UserError('ผลการตรวจสอบ %s\n\n%s' % (self.db_name, message))

    # ============================================================
    # หา config ของพนักงาน 1 คน
    # ============================================================
    @api.model
    def get_for_employee(self, employee):
        if not employee:
            raise UserError('ไม่พบข้อมูลพนักงานในคำขอนี้')
        if not employee.company:
            raise UserError(
                'พนักงาน %s ยังไม่ได้ระบุ "บริษัท" ในทะเบียนพนักงาน '
                'ระบบจึงไม่รู้ว่าต้องส่งใบเบิกไปที่ฐานข้อมูลไหน'
                % (employee.display_name or ''))
        cfg = self.sudo().search([('company', '=', employee.company)], limit=1)
        if not cfg:
            raise UserError(
                'ยังไม่ได้ตั้งค่าปลายทางของบริษัท "%s"\n\n'
                'ไปที่เมนู "ตั้งค่าส่งค่ารักษาพยาบาลเข้าการรับ" '
                'แล้วเพิ่มการตั้งค่าของบริษัทนี้ก่อน' % employee.company)
        return cfg

    # ============================================================
    # สร้างใบการรับ + post
    # ============================================================
    def create_voucher_for_expense(self, expense):
        """สร้างใบการรับใน DB ปลายทางแล้ว post — คืน dict ของผลลัพธ์"""
        self.ensure_one()
        employee = expense.employee_id
        full_name = ' '.join(filter(None, [
            employee.prefix_th or '',
            employee.firstname or '',
            employee.lastname or '',
        ])).strip() or (expense.username or '')

        branch_name = employee.branch_id.name if employee.branch_id else ''
        attachments = self._collect_attachments(expense)
        today = fields.Date.context_today(self)

        with self._target_env() as env:
            partner = self._find_or_create_partner(env, employee, full_name)
            branch_id = self._resolve_branch(env, branch_name)
            analytic_id = self._resolve_analytic()

            line_vals = {
                'name': self.line_label,
                'account_id': self.target_account_id,
                'price_unit': expense.amount,
                'quantity': 1.0,
                'company_id': self.target_company_id,
            }
            if self.target_product_id:
                line_vals['product_id'] = self.target_product_id
            if analytic_id:
                line_vals['account_analytic_id'] = analytic_id

            vals = {
                'voucher_type': 'purchase',
                'date': today,
                'account_date': today,
                'journal_id': self.target_journal_id,
                'partner_id': partner.id,
                'reference': self.reference_text,
                'narration': expense.user_note or '',
                'pay_now': 'pay_now',
                'company_id': self.target_company_id,
                'branch_id': branch_id,
                'payment_method_id': self.target_payment_method_id,
                # 2 ฟิลด์นี้มีครบทุกฐาน จึงตั้งตรง ๆ ไม่เช็ค _fields
                # (เคยเช็คแล้วเจอกรณีคีย์หายเงียบ ๆ จนหาสาเหตุไม่เจอ)
                'head_office_branch_id': branch_id,
                'check_type_show_selection': 'false',
            }
            if self.target_payment_journal_id:
                vals['payment_journal_id'] = self.target_payment_journal_id

            Voucher = env['account.voucher'].with_context(
                allowed_company_ids=[self.target_company_id])

            # payment_date ในบรรทัดบิลไม่มีในทุกฐาน (โลจิสติกส์ไม่มี)
            # ลองใส่ก่อน ถ้าไม่ผ่านค่อยตัดออกแล้วลองใหม่
            voucher = False
            last_error = None
            for candidate in (dict(line_vals, payment_date=today), line_vals):
                try:
                    voucher = Voucher.create(dict(vals, line_ids=[(0, 0, candidate)]))
                    break
                except Exception as e:
                    last_error = e
                    _logger.warning('สร้างใบการรับใน %s ไม่สำเร็จ (line keys=%s): %s',
                                    self.db_name, sorted(candidate.keys()), e)
            if not voucher:
                raise UserError(
                    'สร้างใบการรับในระบบบัญชีของ %s ไม่สำเร็จ\n\n%s'
                    % (self.db_name, last_error))

            # post เพื่อให้ได้เลขเอกสาร + ลงบัญชีจริง
            voucher.proforma_voucher()

            self._push_attachments(env, voucher, attachments)

            number = voucher.number or ''
            result = {
                'db': self.db_name,
                'voucher_id': voucher.id,
                'number': number,
                'state': voucher.state,
                'partner': partner.name,
            }

        if not result['number']:
            _logger.warning(
                'Medical expense #%s: สร้างใบการรับแล้วแต่ไม่ได้เลขเอกสาร (voucher id=%s)',
                expense.id, result['voucher_id'])
        return result

    # ============================================================
    # ยกเลิกใบการรับ (ใช้ตอนถอยกลับ)
    # ============================================================
    def cancel_voucher(self, voucher_id):
        """ยกเลิกใบการรับใน DB ปลายทาง — คืน True ถ้ายกเลิกสำเร็จ/ยกเลิกอยู่แล้ว"""
        self.ensure_one()
        if not voucher_id:
            return False
        with self._target_env() as env:
            voucher = env['account.voucher'].browse(voucher_id).exists()
            if not voucher:
                # ใบถูกลบไปแล้ว ถือว่าไม่มีอะไรค้าง
                return True
            if voucher.state == 'cancel':
                return True
            if voucher.state == 'transferred':
                raise UserError(
                    'ใบการรับ %s ถูกทำจ่าย/โอนเงินไปแล้ว ยกเลิกอัตโนมัติไม่ได้\n'
                    'กรุณาให้ฝ่ายบัญชียกเลิกการโอนในระบบ %s ก่อน'
                    % (voucher.number or voucher.id, self.db_name))
            voucher.cancel_voucher()
            return voucher.state == 'cancel'

    # ============================================================
    # helper
    # ============================================================
    def _find_or_create_partner(self, env, employee, full_name):
        """หาผู้จำหน่ายของพนักงานคนนี้ ไม่เจอก็สร้างใหม่

        ผู้จำหน่ายที่ฝ่ายบัญชีสร้างไว้เดิมเก็บชื่อแบบ "ชื่อ นามสกุล" ไม่มีคำนำหน้า
        ถ้าค้นด้วยชื่อที่มี "นาย/นาง/นางสาว" นำหน้าจะไม่เจอ แล้วสร้างซ้ำทุกครั้ง
        จึงต้องลองทั้งสองแบบ และสร้างใหม่ตามรูปแบบเดิมของฐานนั้น
        """
        Partner = env['res.partner']
        bare_name = ' '.join(filter(None, [
            (employee.firstname or '').strip(),
            (employee.lastname or '').strip(),
        ])).strip()

        candidates = [n for n in (bare_name, (full_name or '').strip()) if n]
        if not candidates:
            raise UserError('ไม่ทราบชื่อพนักงาน จึงระบุผู้จำหน่ายในใบการรับไม่ได้')

        for name in candidates:
            partner = Partner.search(
                [('name', '=', name), ('supplier_rank', '>', 0)], limit=1)
            if partner:
                return partner
        for name in candidates:
            partner = Partner.search([('name', '=', name)], limit=1)
            if partner:
                return partner

        # ---- ไม่มีในระบบ ต้องสร้างใหม่ ----
        # ฐานบัญชีเหล่านี้บังคับกรอกเบอร์โทรและเลขประจำตัวผู้เสียภาษี
        # เช็คก่อนสร้าง จะได้บอกได้ว่าต้องไปเติมข้อมูลที่ไหน
        # ไม่ใช่ปล่อยให้เด้ง Validation Error ดิบ ๆ ที่ไม่บอกว่าต้องแก้ตรงไหน
        phone = (employee.phone_number or '').strip()
        id_card = (employee.id_card_number or '').strip()
        email = (employee.email or '').strip()
        missing = []
        if not phone:
            missing.append('เบอร์โทรศัพท์')
        if not id_card:
            # เลขผู้เสียภาษีของบุคคลธรรมดาคือเลขบัตรประชาชน
            # ห้ามเอาเบอร์โทรไปใส่แทน ข้อมูลในระบบบัญชีจะเพี้ยน
            missing.append('เลขประจำตัวประชาชน')
        if not email:
            # โมดูล partner_email_required บังคับไว้ทุกฐาน พร้อมตรวจรูปแบบ
            missing.append('อีเมล')
        if missing:
            raise UserError(
                'ยังไม่มีผู้จำหน่ายชื่อ "%s" ในระบบบัญชีของ %s\n'
                'ระบบจะสร้างให้อัตโนมัติ แต่ฐานนี้บังคับกรอก %s\n\n'
                'กรุณาเติมข้อมูลนี้ในทะเบียนพนักงานก่อน แล้วกดอนุมัติอีกครั้ง'
                % (bare_name or full_name, self.db_name, ' และ '.join(missing)))

        partner_name = bare_name or full_name
        base_vals = {
            'name': partner_name,
            'is_company': False,
            'supplier_rank': 1,
            'phone': phone,
            'vat': id_card,
            'email': email,
        }
        # grant_role / grant_type มาจากโมดูลเสริม ฐานที่ไม่มีจะ create ไม่ผ่าน
        # จึงลองใส่ก่อน ถ้าไม่ผ่านค่อยตัดออกแล้วลองใหม่ — ไม่พึ่ง _fields
        # เพราะเคยกรองคีย์หายจนหา error จริงไม่เจอ
        attempts = [
            dict(base_vals, grant_role='reader', grant_type='user'),
            base_vals,
        ]

        partner = False
        last_error = None
        for vals in attempts:
            try:
                partner = Partner.create(vals)
                break
            except Exception as e:
                last_error = e
                _logger.warning(
                    'สร้างผู้จำหน่าย "%s" ใน %s ไม่สำเร็จ (keys=%s): %s',
                    partner_name, self.db_name, sorted(vals.keys()), e)

        if not partner:
            raise UserError(
                'สร้างผู้จำหน่าย "%s" ในระบบบัญชีของ %s ไม่สำเร็จ\n\n%s\n\n'
                'กรุณาให้ฝ่ายบัญชีสร้างผู้จำหน่ายรายนี้ก่อน แล้วกดอนุมัติอีกครั้ง'
                % (partner_name, self.db_name, last_error))

        _logger.info('สร้างผู้จำหน่ายใหม่ใน %s: %s (id=%s)',
                     self.db_name, partner_name, partner.id)
        return partner

    def _resolve_branch(self, env, branch_name):
        """จับคู่สาขาของพนักงานกับ res.branch ปลายทางด้วยชื่อ ไม่เจอใช้สาขาเริ่มต้น"""
        if branch_name:
            branch = env['res.branch'].search([('name', '=', branch_name)], limit=1)
            if branch:
                return branch.id
        return self.target_default_branch_id

    def _resolve_analytic(self):
        """บัญชีวิเคราะห์ของใบเบิกค่ารักษาพยาบาล — ใช้ค่าที่ตั้งไว้เสมอ

        เดิมจับคู่ตามสาขาของพนักงาน แต่ฝ่ายบัญชีต้องการให้ลงสำนักงานใหญ่
        ที่เดียวทั้งหมด เพราะเป็นสวัสดิการระดับบริษัท ไม่ใช่ต้นทุนของสาขา
        ตัวเลขมาจากช่อง "บัญชีวิเคราะห์" ในเมนูตั้งค่า — เปลี่ยนที่นั่นได้
        โดยไม่ต้องแก้โค้ด
        """
        return self.target_analytic_id or False

    def _collect_attachments(self, expense):
        """รวมไฟล์แนบทั้งหมดเป็น [(ชื่อไฟล์, base64)] ก่อนข้าม DB

        ไฟล์จากแอปอยู่บนเซิร์ฟเวอร์ PHP ต้องโหลดมาก่อน ส่วนไฟล์ที่แนบใน Odoo
        อ่านจาก ir.attachment ของ DB ปัจจุบันได้เลย
        """
        collected = []
        seen_ids = set()

        # ไฟล์จากแอปถูกโหลดมาเก็บเป็นเอกสารแนบของคำขอตั้งแต่ตอนซิงค์แล้ว
        # ใช้ของที่เก็บไว้ ไม่ต้องไปโหลดจาก PHP ซ้ำตอนกดอนุมัติ
        stored = expense.env['ir.attachment'].sudo().search([
            ('res_model', '=', expense._name),
            ('res_id', '=', expense.id),
        ])
        for attachment in stored | expense.attachment_ids:
            if attachment.id in seen_ids or not attachment.datas:
                continue
            seen_ids.add(attachment.id)
            collected.append((attachment.name or 'attachment', attachment.datas))

        if collected:
            return collected

        # ใบเก่าที่ซิงค์มาก่อนมีฟีเจอร์นี้ยังไม่มีไฟล์เก็บไว้ — ถอยไปโหลดจาก PHP
        for line in expense.attachment_line_ids:
            url = line._build_url()
            if not url:
                continue
            try:
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                collected.append((line.name or url.split('/')[-1],
                                  base64.b64encode(response.content)))
            except requests.exceptions.RequestException as e:
                _logger.warning('โหลดไฟล์แนบไม่สำเร็จ (%s): %s', url, e)

        return collected

    def _push_attachments(self, env, voucher, attachments):
        for name, datas in attachments:
            try:
                env['ir.attachment'].create({
                    'name': name,
                    'datas': datas,
                    'res_model': 'account.voucher',
                    'res_id': voucher.id,
                    'company_id': self.target_company_id,
                })
            except Exception as e:
                # ไฟล์แนบพลาดไม่ควรทำให้ใบการรับที่ post แล้วล้ม
                _logger.warning('แนบไฟล์ "%s" เข้าใบ %s ไม่สำเร็จ: %s',
                                name, voucher.id, e)
