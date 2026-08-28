# -*- coding: utf-8 -*-
import odoo
from odoo import models, fields, api, _
from datetime import date, timedelta
import logging

try:
    from bahttext import bahttext
except ImportError:
    bahttext = None

_logger = logging.getLogger(__name__)

# เริ่มดึงข้อมูลหนี้ตั้งแต่ปี 2026 เป็นต้นไป (ข้อมูลปีต่ำกว่า 2026 จะไม่ถูกดึง/ถูกล้างออก)
DEBT_START_DATE = date(2026, 1, 1)
DEBT_START_STR = '2026-01-01'

# ----------------------------------------------------------------------------
# ประเภทเอกสาร (scrap.reason.code) -- ใช้แยกว่าใบแจ้งหนี้ใบไหนไปอยู่แท็บอะไร
# ผู้ใช้ระบุ 19 ส.ค. 2026: "ประเภทการชำระบอกว่าหน้ารวมหนี้ลูกค้ามีกี่แท็บ"
# เดิมแท็บใบแจ้งหนี้ดึงมารวมกันหมด ทำให้ค่าปรับหาย/ชำรุดถูกนับซ้ำสองที่
# ใบที่ไม่ได้ระบุประเภทให้ถือเป็นค่าเช่า (ค่า default ของฟิลด์คือค่าเช่าอยู่แล้ว)
# ----------------------------------------------------------------------------
# ค่าขนส่งอยู่คนละฐานข้อมูล (บริษัทขนส่งเป็นอีกบริษัทหนึ่ง)
# ใบสั่งขายฝั่งขนส่งเก็บไว้ว่ารับงานเช่ามาจาก DB ไหน (database_selection)
# และเลขเอกสาร SO ต้นทางคืออะไร (so_number) จับคู่ 2 ฟิลด์นี้เพื่อหาใบแจ้งหนี้ค่าขนส่ง
TRANSPORT_DB = 'NPD_Logistics_New'

REASON_RENT = u'ใบแจ้งหนี้ค่าเช่า'
REASON_RENT_DIFF = u'ค่าเช่าส่วนต่าง'
REASON_LOST = u'สินค้าหาย'
REASON_DAMAGE = u'สินค้าชำรุด'

# ----------------------------------------------------------------------------
# เลขที่เอกสาร -- คำนำหน้าแยกตามฐานข้อมูล (แต่ละบริษัทอยู่คนละ DB)
# รูปแบบ: <คำนำหน้า> <เลขรัน 4 หลัก>/<ปี พ.ศ.>  เช่น NPS.N 0001/2569
# (ของเดิมเป็น DEBT-2026-00273 เปลี่ยนตามที่ผู้ใช้ระบุ 19 ส.ค. 2026)
# ----------------------------------------------------------------------------
DB_DOC_PREFIX = {
    'NPD_S_Group_New_V2': 'NPD.N',
    'NPD_Intertrading_New': 'NPI.N',
    'NPD_Steeltech_New': 'NPS.N',
    'NPD_Bangkok_New': 'NBK.N',
    'NPD_Logistics_New': 'NPL.N',
}
# DB ที่ไม่อยู่ในตาราง (เช่น DB ที่ copy ไปทดสอบ ชื่อจะมีหางต่อท้าย) จะเทียบแบบ
# ขึ้นต้นตรงกันให้ ถ้ายังไม่ตรงอีกค่อยใช้ค่านี้
DEFAULT_DOC_PREFIX = 'NPD.N'
# ตั้ง System Parameter ตัวนี้เพื่อบังคับคำนำหน้าเอง (สำคัญกว่าตารางข้างบน)
DOC_PREFIX_PARAM = 'npd_debt_summary.doc_prefix'


class NpdDebtSummary(models.Model):
    _name = 'npd.debt.summary'
    _description = 'รวมหนี้ลูกค้า'
    _order = 'partner_name asc'
    _rec_name = 'display_name'

    name = fields.Char(string='เลขที่เอกสาร', default='New', readonly=True, copy=False, index=True,
        help='เลขที่เอกสารสรุปหนี้รวมของลูกค้า')
    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)

    @api.depends('name', 'partner_name')
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_name and rec.name and rec.name != 'New':
                rec.display_name = '%s - %s' % (rec.name, rec.partner_name)
            else:
                rec.display_name = rec.name or rec.partner_name or 'New'

    # เก็บไว้เพื่อความเข้ากันได้กับรายงาน (ไม่แสดงในฟอร์ม)
    note = fields.Text(string='หมายเหตุ')

    customer_id = fields.Many2one('res.partner', string='ลูกค้า', required=True, ondelete='cascade',
        index=True, help='ลูกค้า (Commercial Partner)')
    partner_name = fields.Char(string='ชื่อลูกค้า', store=True)
    partner_phone = fields.Char(string='เบอร์โทรศัพท์')
    partner_mobile = fields.Char(string='มือถือ')
    partner_email = fields.Char(string='อีเมล')
    partner_vat = fields.Char(string='เลขที่ผู้เสียภาษี')
    partner_street = fields.Char(string='ที่อยู่')
    partner_street2 = fields.Char(string='ที่อยู่ 2')
    partner_city = fields.Char(string='เมือง')
    partner_state_id = fields.Many2one('res.country.state', string='จังหวัด')
    partner_zip = fields.Char(string='รหัสไปรษณีย์')

    company_id = fields.Many2one('res.company', string='บริษัท',
        default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one('res.currency', string='สกุลเงิน',
        default=lambda self: self.env.company.currency_id)

    last_update = fields.Datetime(string='อัพเดทล่าสุด', readonly=True)

    _sql_constraints = [
        ('customer_uniq', 'unique(customer_id)', 'ลูกค้าแต่ละรายต้องมีได้เพียงรายการเดียว'),
    ]

    # ===== ใบแจ้งหนี้ค้างชำระ =====
    customer_invoice_line_ids = fields.One2many('npd.debt.summary.invoice.line',
        'summary_id', string='ใบแจ้งหนี้ค้างชำระทั้งหมด')
    customer_amount_residual = fields.Monetary(string='ยอดค้างชำระใบแจ้งหนี้',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ใบแจ้งหนี้ค่าประกัน =====
    customer_deposit_line_ids = fields.One2many('npd.debt.summary.deposit.line',
        'summary_id', string='ใบแจ้งหนี้ค่าประกันทั้งหมด')
    customer_deposit_residual = fields.Monetary(string='ค้างชำระค่าประกัน',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่าเช่าส่วนต่าง =====
    customer_rentdiff_line_ids = fields.One2many('npd.debt.summary.rentdiff.line',
        'summary_id', string='ค่าเช่าส่วนต่างทั้งหมด')
    customer_rentdiff_residual = fields.Monetary(string='ค้างชำระค่าเช่าส่วนต่าง',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่าปรับหาย =====
    customer_penalty_line_ids = fields.One2many('npd.debt.summary.penalty.line',
        'summary_id', string='ค่าปรับหายทั้งหมด')
    customer_penalty_residual = fields.Monetary(string='ค้างชำระค่าปรับหาย',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่าปรับชำรุด =====
    customer_damage_line_ids = fields.One2many('npd.debt.summary.damage.line',
        'summary_id', string='ค่าปรับชำรุดทั้งหมด')
    customer_damage_residual = fields.Monetary(string='ค้างชำระค่าปรับชำรุด',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่าขนส่ง (ข้ามฐานข้อมูลไปเอาจากบริษัทขนส่ง) =====
    customer_transport_line_ids = fields.One2many('npd.debt.summary.transport.line',
        'summary_id', string='ค่าขนส่งทั้งหมด')
    customer_transport_residual = fields.Monetary(string='ค้างชำระค่าขนส่ง',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่าหัก ณ ที่จ่าย =====
    customer_tax_line_ids = fields.One2many('npd.debt.summary.tax.line',
        'summary_id', string='ค่าหัก ณ ที่จ่ายทั้งหมด')
    customer_tax_residual = fields.Monetary(string='ค้างชำระค่าหัก ณ ที่จ่าย',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    @api.depends('customer_invoice_line_ids.amount_residual', 'customer_invoice_line_ids.payment_status',
                 'customer_deposit_line_ids.amount_residual', 'customer_deposit_line_ids.payment_status',
                 'customer_rentdiff_line_ids.amount_residual', 'customer_rentdiff_line_ids.payment_status',
                 'customer_penalty_line_ids.amount_residual', 'customer_penalty_line_ids.payment_status',
                 'customer_damage_line_ids.amount_residual', 'customer_damage_line_ids.payment_status',
                 'customer_transport_line_ids.amount_residual', 'customer_transport_line_ids.payment_status',
                 'customer_tax_line_ids.tax_amount', 'customer_tax_line_ids.payment_status')
    def _compute_residuals(self):
        for rec in self:
            rec.customer_amount_residual = sum(
                l.amount_residual for l in rec.customer_invoice_line_ids if l.payment_status == 'unpaid')
            rec.customer_deposit_residual = sum(
                l.amount_residual for l in rec.customer_deposit_line_ids if l.payment_status == 'unpaid')
            rec.customer_rentdiff_residual = sum(
                l.amount_residual for l in rec.customer_rentdiff_line_ids if l.payment_status == 'unpaid')
            rec.customer_penalty_residual = sum(
                l.amount_residual for l in rec.customer_penalty_line_ids if l.payment_status == 'unpaid')
            rec.customer_damage_residual = sum(
                l.amount_residual for l in rec.customer_damage_line_ids if l.payment_status == 'unpaid')
            rec.customer_transport_residual = sum(
                l.amount_residual for l in rec.customer_transport_line_ids if l.payment_status == 'unpaid')
            rec.customer_tax_residual = sum(
                l.tax_amount for l in rec.customer_tax_line_ids if l.payment_status == 'unpaid')

    grand_total = fields.Monetary(string='รวมหนี้ทั้งสิ้น', currency_field='currency_id',
        compute='_compute_grand_total', store=True)

    payment_status = fields.Selection([
        ('unpaid', 'ค้างชำระ'),
        ('paid', 'ชำระแล้ว'),
    ], string='สถานะรวม', compute='_compute_payment_status', store=True, default='unpaid')

    # สถานะแยกตามแต่ละแท็บ
    invoice_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะใบแจ้งหนี้', compute='_compute_payment_status', store=True)
    deposit_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าประกัน', compute='_compute_payment_status', store=True)
    rentdiff_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าเช่าส่วนต่าง', compute='_compute_payment_status', store=True)
    lost_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าปรับหาย', compute='_compute_payment_status', store=True)
    damage_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าปรับชำรุด', compute='_compute_payment_status', store=True)
    transport_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าขนส่ง', compute='_compute_payment_status', store=True)
    tax_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าหัก ณ ที่จ่าย', compute='_compute_payment_status', store=True)

    @api.depends('customer_invoice_line_ids.payment_status',
                 'customer_deposit_line_ids.payment_status',
                 'customer_rentdiff_line_ids.payment_status',
                 'customer_penalty_line_ids.payment_status',
                 'customer_damage_line_ids.payment_status',
                 'customer_transport_line_ids.payment_status',
                 'customer_tax_line_ids.payment_status')
    def _compute_payment_status(self):
        for rec in self:
            inv_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_invoice_line_ids)
            dep_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_deposit_line_ids)
            diff_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_rentdiff_line_ids)
            pen_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_penalty_line_ids)
            dmg_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_damage_line_ids)
            trn_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_transport_line_ids)
            tax_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_tax_line_ids)
            rec.invoice_payment_status = 'unpaid' if inv_unpaid else 'paid'
            rec.deposit_payment_status = 'unpaid' if dep_unpaid else 'paid'
            rec.rentdiff_payment_status = 'unpaid' if diff_unpaid else 'paid'
            rec.lost_payment_status = 'unpaid' if pen_unpaid else 'paid'
            rec.damage_payment_status = 'unpaid' if dmg_unpaid else 'paid'
            rec.transport_payment_status = 'unpaid' if trn_unpaid else 'paid'
            rec.tax_payment_status = 'unpaid' if tax_unpaid else 'paid'
            rec.payment_status = 'unpaid' if (inv_unpaid or dep_unpaid or diff_unpaid
                                              or pen_unpaid or dmg_unpaid or trn_unpaid
                                              or tax_unpaid) else 'paid'

    # ===== วันที่/วันครบกำหนดชำระ ของแต่ละประเภท (คำนวณจากรายการล่าสุด + 14 วัน) =====
    invoice_report_date = fields.Date(string='วันที่ (ใบแจ้งหนี้)',
        compute='_compute_report_dates', store=True)
    invoice_due_date = fields.Date(string='วันที่กำหนดชำระ (ใบแจ้งหนี้)',
        compute='_compute_report_dates', store=True)
    deposit_report_date = fields.Date(string='วันที่ (ค่าประกัน)',
        compute='_compute_report_dates', store=True)
    deposit_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าประกัน)',
        compute='_compute_report_dates', store=True)
    rentdiff_report_date = fields.Date(string='วันที่ (ค่าเช่าส่วนต่าง)',
        compute='_compute_report_dates', store=True)
    rentdiff_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าเช่าส่วนต่าง)',
        compute='_compute_report_dates', store=True)
    lost_report_date = fields.Date(string='วันที่ (ค่าปรับหาย)',
        compute='_compute_report_dates', store=True)
    lost_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าปรับหาย)',
        compute='_compute_report_dates', store=True)
    damage_report_date = fields.Date(string='วันที่ (ค่าปรับชำรุด)',
        compute='_compute_report_dates', store=True)
    damage_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าปรับชำรุด)',
        compute='_compute_report_dates', store=True)
    transport_report_date = fields.Date(string='วันที่ (ค่าขนส่ง)',
        compute='_compute_report_dates', store=True)
    transport_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าขนส่ง)',
        compute='_compute_report_dates', store=True)
    tax_report_date = fields.Date(string='วันที่ (ค่าหัก ณ ที่จ่าย)',
        compute='_compute_report_dates', store=True)
    tax_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าหัก ณ ที่จ่าย)',
        compute='_compute_report_dates', store=True)

    @api.depends('customer_transport_line_ids.invoice_date',
                 'customer_deposit_line_ids.invoice_date',
                 'customer_rentdiff_line_ids.invoice_date',
                 'customer_invoice_line_ids.invoice_date',
                 'customer_penalty_line_ids.rental_start_date',
                 'customer_damage_line_ids.rental_start_date',
                 'customer_tax_line_ids.invoice_date')
    def _compute_report_dates(self):
        for rec in self:
            inv_dates = [l.invoice_date for l in rec.customer_invoice_line_ids if l.invoice_date]
            rec.invoice_report_date = max(inv_dates) if inv_dates else False
            rec.invoice_due_date = (rec.invoice_report_date + timedelta(days=14)) if rec.invoice_report_date else False

            # ค่าประกัน: คิดแบบเดียวกับใบแจ้งหนี้ค่าเช่า
            dep_dates = [l.invoice_date for l in rec.customer_deposit_line_ids if l.invoice_date]
            rec.deposit_report_date = max(dep_dates) if dep_dates else False
            rec.deposit_due_date = ((rec.deposit_report_date + timedelta(days=14))
                                    if rec.deposit_report_date else False)

            # ค่าเช่าส่วนต่าง: คิดแบบเดียวกับใบแจ้งหนี้ค่าเช่า
            diff_dates = [l.invoice_date for l in rec.customer_rentdiff_line_ids if l.invoice_date]
            rec.rentdiff_report_date = max(diff_dates) if diff_dates else False
            rec.rentdiff_due_date = ((rec.rentdiff_report_date + timedelta(days=14))
                                     if rec.rentdiff_report_date else False)

            # ค่าปรับหาย: วันที่ = วันที่ใบแจ้งหนี้ล่าสุด, วันกำหนดชำระ = +14 วัน
            pen_dates = [l.rental_start_date for l in rec.customer_penalty_line_ids if l.rental_start_date]
            rec.lost_report_date = max(pen_dates) if pen_dates else False
            rec.lost_due_date = (rec.lost_report_date + timedelta(days=14)) if rec.lost_report_date else False

            # ค่าปรับชำรุด: วันที่ = วันที่ใบแจ้งหนี้ล่าสุด, วันกำหนดชำระ = +14 วัน
            dmg_dates = [l.rental_start_date for l in rec.customer_damage_line_ids if l.rental_start_date]
            rec.damage_report_date = max(dmg_dates) if dmg_dates else False
            rec.damage_due_date = (rec.damage_report_date + timedelta(days=14)) if rec.damage_report_date else False

            trn_dates = [l.invoice_date for l in rec.customer_transport_line_ids if l.invoice_date]
            rec.transport_report_date = max(trn_dates) if trn_dates else False
            rec.transport_due_date = ((rec.transport_report_date + timedelta(days=14))
                                      if rec.transport_report_date else False)

            tax_dates = [l.invoice_date for l in rec.customer_tax_line_ids if l.invoice_date]
            rec.tax_report_date = max(tax_dates) if tax_dates else False
            rec.tax_due_date = (rec.tax_report_date + timedelta(days=14)) if rec.tax_report_date else False

    @api.depends('customer_amount_residual', 'customer_deposit_residual',
                 'customer_rentdiff_residual', 'customer_penalty_residual',
                 'customer_damage_residual', 'customer_transport_residual',
                 'customer_tax_residual')
    def _compute_grand_total(self):
        for rec in self:
            rec.grand_total = (rec.customer_amount_residual + rec.customer_deposit_residual
                               + rec.customer_rentdiff_residual + rec.customer_penalty_residual
                               + rec.customer_damage_residual + rec.customer_transport_residual
                               + rec.customer_tax_residual)

    # ===== เลขที่เอกสาร =====
    @api.model
    def _debt_doc_prefix(self):
        """คำนำหน้าเลขที่เอกสารของ DB ที่กำลังใช้งานอยู่

        ลำดับการหา: System Parameter -> ชื่อ DB ตรงตัว -> ชื่อ DB ขึ้นต้นตรงกัน
        (เผื่อ DB ที่ copy ไปทดสอบ เช่น NPD_Steeltech_New_test) -> ค่าเริ่มต้น
        """
        param = self.env['ir.config_parameter'].sudo().get_param(DOC_PREFIX_PARAM)
        if param:
            return param.strip()
        dbname = self.env.cr.dbname or ''
        if dbname in DB_DOC_PREFIX:
            return DB_DOC_PREFIX[dbname]
        # เทียบแบบขึ้นต้น เอาชื่อที่ยาวที่สุดก่อน กันกรณีชื่อซ้อนกัน
        for key in sorted(DB_DOC_PREFIX, key=len, reverse=True):
            if dbname.startswith(key):
                return DB_DOC_PREFIX[key]
        _logger.warning(
            u'npd_debt_summary: ไม่รู้จัก DB %s ใช้คำนำหน้า %s ไปก่อน '
            u'(ตั้ง System Parameter %s เพื่อกำหนดเอง)',
            dbname, DEFAULT_DOC_PREFIX, DOC_PREFIX_PARAM)
        return DEFAULT_DOC_PREFIX

    @api.model
    def _next_debt_doc_name(self):
        """เลขที่เอกสารใบถัดไป เช่น NPS.N 0001/2569

        เลขรันมาจาก ir.sequence (padding 4, ไม่มี prefix) ที่เปิด use_date_range
        ไว้ Odoo จึงตัดรอบให้เองทุกปี ขึ้นปีใหม่เลขจะกลับไปเริ่ม 0001
        ส่วนปีที่ต่อท้ายเป็น พ.ศ. = ค.ศ. + 543
        """
        number = self.env['ir.sequence'].next_by_code('npd.debt.summary')
        if not number:
            return 'New'
        return '%s %s/%s' % (self._debt_doc_prefix(), number,
                             fields.Date.context_today(self).year + 543)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') in (False, 'New'):
            vals['name'] = self._next_debt_doc_name()
        return super().create(vals)

    def action_renumber_documents(self):
        """ออกเลขที่เอกสารใหม่ให้ record เก่าที่ยังเป็นรูปแบบ DEBT-xxxx

        ไม่ได้เรียกเองอัตโนมัติ -- ใช้ตอนที่ต้องการให้เลขในระบบเป็นรูปแบบใหม่
        ทั้งหมด เรียงตามลำดับการสร้าง (id) แล้วไล่เลขใหม่ตั้งแต่ 0001
        """
        records = self.search([], order='id asc')
        prefix = self._debt_doc_prefix()
        year_be = fields.Date.context_today(self).year + 543
        seq = self.env['ir.sequence'].search(
            [('code', '=', 'npd.debt.summary')], limit=1)
        running = 0
        for rec in records:
            running += 1
            rec.name = '%s %04d/%s' % (prefix, running, year_be)
        # ให้ ir.sequence เดินต่อจากเลขสุดท้ายที่เพิ่งไล่ไป
        if seq and running:
            date_range = seq.date_range_ids.filtered(
                lambda r: r.date_from.year == fields.Date.context_today(self).year)
            if date_range:
                date_range.number_next_actual = running + 1
            else:
                seq.number_next_actual = running + 1
        _logger.info(u'npd_debt_summary: ออกเลขใหม่ %s ใบ (%s 0001/%s เป็นต้นไป)',
                     running, prefix, year_be)
        return True

    # ===== baht text (สำหรับรายงาน) =====
    def _baht(self, amount):
        if bahttext:
            return bahttext(amount or 0.0)
        return '{:,.2f} บาท'.format(amount or 0.0)

    def get_total_baht_text_sheet(self):
        return self._baht(self.customer_amount_residual)

    def get_lost_baht_text_sheet(self):
        return self._baht(self.customer_penalty_residual)

    def get_damage_baht_text_sheet(self):
        return self._baht(self.customer_damage_residual)

    def get_total_baht_text_sheet_tax(self):
        return self._baht(self.customer_tax_residual)

    def get_amount_residual_formatted(self):
        return '{:,.2f}'.format(self.customer_amount_residual)

    def get_amount_lost_formatted(self):
        return '{:,.2f}'.format(self.customer_penalty_residual)

    def get_amount_damage_formatted(self):
        return '{:,.2f}'.format(self.customer_damage_residual)

    def get_amount_tax_formatted(self):
        return '{:,.2f}'.format(self.customer_tax_residual)

    # =========================================================================
    #  ค้นหาลูกค้าที่เข้าเงื่อนไข + สร้าง/อัพเดท record  (เรียกจากเมนู/ปุ่มอัพเดท)
    # =========================================================================
    @api.model
    def _get_overdue_partner_ids(self):
        """คืน commercial partner ids ที่มีใบแจ้งหนี้ลูกค้าค้างชำระ (ไม่ว่าถึงกำหนดหรือยัง)"""
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('amount_residual', '>', 0),
            ('invoice_date', '>=', DEBT_START_STR),
        ])
        partner_ids = set()
        for inv in invoices:
            p = inv.partner_id.commercial_partner_id or inv.partner_id
            if p:
                partner_ids.add(p.id)
        return list(partner_ids)

    @api.model
    def _fix_stale_invoice_residuals(self):
        """ล้างยอดค้างที่ล้าสมัยของใบแจ้งหนี้ก่อนดึงข้อมูล

        amount_residual กับ payment_state เป็นฟิลด์ compute แบบ store
        ถ้าไปแก้วันที่บนใบที่ลงบัญชี (posted) แล้ว Odoo ไม่ได้สั่งคำนวณใหม่
        ค่าที่เก็บไว้จึงค้างของเดิม (ต้องรีเซ็ตเป็นร่างแล้วโพสต์ใหม่ถึงจะอัพเดท)

        อาการที่ตรวจจับได้คือใบที่ payment_state = paid แต่ amount_residual
        ยังมากกว่า 0 -- แบบนี้คือยอดค้างล้าสมัย ไม่ใช่หนี้จริง
        ถ้าไม่ล้างก่อน รวมหนี้ลูกค้าจะโชว์หนี้ที่ชำระไปแล้ว
        (ตรวจข้อมูลจริง 21 ส.ค. 2026 เจอ 22 ใบ รวม 152,751 บาท)
        """
        moves = self.env['account.move'].search([
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('payment_state', '=', 'paid'),
            ('amount_residual', '>', 0.005),
        ])
        if moves:
            moves._compute_amount()
            _logger.info(u'npd_debt_summary: ล้างยอดค้างล้าสมัย %s ใบ', len(moves))
        return len(moves)

    @api.model
    def cron_refresh_all(self):
        """อัพเดทข้อมูลทุกลูกค้า (เรียกจาก Scheduled Action ทุกวันตี 3)"""
        self._fix_stale_invoice_residuals()
        self._refresh_all_records()

    @api.model
    def action_refresh_all(self):
        """อัพเดททั้งหมดแล้วเปิดรายการ (สำหรับเรียกเองเมื่อต้องการ)"""
        self._fix_stale_invoice_residuals()
        self._refresh_all_records()
        return {
            'type': 'ir.actions.act_window',
            'name': _('รวมหนี้ลูกค้า'),
            'res_model': 'npd.debt.summary',
            'view_mode': 'tree,form',
            'search_view_id': self.env.ref('npd_debt_summary.npd_debt_summary_view_search').id,
            'context': {},
            'target': 'current',
        }

    @api.model
    def _refresh_all_records(self):
        """สแกน + อัพเดทข้อมูล 4 แท็บของทุกลูกค้า (ไม่ลบลูกค้า — ใช้สถานะแทน)"""
        # ลูกค้าที่มีใบแจ้งหนี้ค้างชำระ (สำหรับเพิ่มลูกค้าใหม่) + ลูกค้าที่มีอยู่แล้ว (อัพเดทซ้ำ)
        partner_ids = set(self._get_overdue_partner_ids())
        existing = self.search([])
        by_customer = {r.customer_id.id: r for r in existing}
        all_ids = partner_ids | set(by_customer.keys())

        for pid in all_ids:
            rec = by_customer.get(pid)
            if not rec:
                rec = self.create({'customer_id': pid})
            rec._populate_customer_data()
        self._remove_empty_records()

    def _is_debt_cleared(self):
        """ลูกค้ารายนี้ไม่ต้องติดตามแล้วหรือยัง

        จริงเมื่อ
        1. ไม่มีรายการหนี้ทั้ง 4 ประเภทเลย (เช่น เหลือแต่หนี้ปีต่ำกว่า 2026
           ที่ถูกกรองออกไปแล้ว) หรือ
        2. ทั้ง 4 ประเภทขึ้น "ชำระแล้ว" หมด และยอดรวมเป็น 0
        """
        self.ensure_one()
        if not (self.customer_invoice_line_ids or self.customer_deposit_line_ids
                or self.customer_rentdiff_line_ids or self.customer_penalty_line_ids
                or self.customer_damage_line_ids or self.customer_transport_line_ids
                or self.customer_tax_line_ids):
            return True
        all_paid = all(status == 'paid' for status in (
            self.invoice_payment_status, self.deposit_payment_status,
            self.rentdiff_payment_status, self.lost_payment_status,
            self.damage_payment_status, self.transport_payment_status,
            self.tax_payment_status))
        return all_paid and abs(self.grand_total or 0.0) < 0.01

    @api.model
    def _remove_empty_records(self):
        """ล้างลูกค้าที่ไม่มีหนี้ค้างแล้วออกจากรายการ

        เดิมเก็บลูกค้าที่จ่ายครบไว้แล้วโชว์สถานะ "ชำระแล้ว"
        เปลี่ยนเป็นเคลียร์ออกเลยตามที่ผู้ใช้ระบุ (19 ส.ค. 2026)
        ถ้าวันหลังลูกค้ามีหนี้ค้างอีก ระบบจะสร้างรายการใหม่ให้เอง
        ตอนกดอัพเดท (ได้เลขที่เอกสารใบใหม่)
        """
        cleared = self.search([]).filtered(lambda r: r._is_debt_cleared())
        if cleared:
            _logger.info(u'npd_debt_summary: เคลียร์ลูกค้าที่ชำระครบแล้ว %s ราย',
                         len(cleared))
            cleared.unlink()

    @api.model
    def action_clear_old_data(self):
        """ล้างข้อมูลหนี้ปีเก่า (ต่ำกว่า 2026) ออกทั้งหมด แล้วดึงข้อมูลใหม่ตั้งแต่ปี 2026
        เรียกครั้งเดียวเพื่อล้างข้อมูลเดิมที่มีอยู่ในระบบ"""
        self._refresh_all_records()
        return True

    def action_refresh_one(self):
        """ปุ่มอัพเดทข้อมูลลูกค้ารายนี้

        ถ้าอัพเดทแล้วพบว่าชำระครบทุกประเภท จะเคลียร์รายการนี้ทิ้งแล้วพากลับไป
        หน้ารายการ (ถ้าปล่อยให้ค้างอยู่หน้าฟอร์มเดิม จอจะฟ้องว่าไม่พบเรคคอร์ด)
        """
        cleared = self.browse()
        for rec in self:
            rec._populate_customer_data()
            if rec._is_debt_cleared():
                cleared |= rec
        if cleared:
            cleared.unlink()
            return {
                'type': 'ir.actions.act_window',
                'name': _('รวมหนี้ลูกค้า'),
                'res_model': 'npd.debt.summary',
                'view_mode': 'tree,form',
                'context': {},
                'target': 'current',
            }
        return True

    @staticmethod
    def _move_reason_name(move):
        """ชื่อประเภทเอกสารของใบแจ้งหนี้ ('' ถ้าไม่ได้ระบุ/ไม่มีฟิลด์)"""
        reason = getattr(move, 'reason_code_id', False)
        return reason.name if reason else ''

    def _deposit_invoice_ids(self, invoices):
        """id ของ 'ใบแจ้งหนี้ค่าประกัน' ในกลุ่มที่ส่งเข้ามา

        ใบค่าประกัน (INS-) ระบุประเภทสินค้าเป็น 'ใบแจ้งหนี้ค่าเช่า' เหมือนใบค่าเช่า
        ปกติ ดูจากประเภทอย่างเดียวจึงแยกไม่ออก ต้องดูที่การผูกกับใบสั่งขายผ่าน
        ตาราง account_move_sale_order_rel (วิธีเดียวกับโมดูล npd_rent_invoice_overdue)
        ตรวจกับข้อมูลจริงแล้วมีแต่ใบ INS เท่านั้นที่ผูกผ่านตารางนี้
        """
        if not invoices:
            return set()
        self._cr.execute("""
            SELECT 1 FROM information_schema.tables
             WHERE table_name = 'account_move_sale_order_rel' LIMIT 1
        """)
        if not self._cr.fetchone():
            return set()   # DB ที่ไม่ได้ติดตั้งโมดูลใบแจ้งหนี้ค่าประกัน
        self._cr.execute("""
            SELECT DISTINCT account_move_id
              FROM account_move_sale_order_rel
             WHERE account_move_id IN %s
        """, (tuple(invoices.ids),))
        return set(row[0] for row in self._cr.fetchall())

    def _build_invoice_line_vals(self, inv, today):
        """ค่าของ 1 บรรทัดในแท็บใบแจ้งหนี้ค่าเช่า / ค่าเช่าส่วนต่าง (โครงเดียวกัน)"""
        inv.invalidate_cache(['amount_residual', 'payment_state'], [inv.id])
        payment_label = dict(
            self.env['account.move']._fields['payment_state'].selection
        ).get(inv.payment_state, inv.payment_state)
        return {
            'invoice_id': inv.id,
            'invoice_name': inv.name,
            'invoice_origin': inv.invoice_origin or '',
            'invoice_date': inv.invoice_date,
            'invoice_date_due': inv.invoice_date_due,
            'amount_total': inv.amount_total,
            'amount_residual': inv.amount_residual,
            'payment_state': inv.payment_state,
            'payment_state_label': payment_label,
            'days_overdue': ((today - inv.invoice_date_due).days
                             if inv.invoice_date_due else 0),
            'product_info_html': self._build_product_html(inv),
        }

    # ------------------------------------------------------------------
    # ค่าขนส่ง -- อยู่คนละฐานข้อมูล ต้องเปิด cursor ไปที่ DB ของบริษัทขนส่ง
    # ------------------------------------------------------------------
    def _transport_debt_rows(self, so_names):
        """ใบแจ้งหนี้ค่าขนส่งที่ยังค้างชำระ ของเลข SO ที่ส่งเข้ามา

        ฝั่งขนส่ง (DB %s) ใบสั่งขายจะบันทึกไว้ว่า
            database_selection = DB ต้นทางที่รับงานเช่ามา
            so_number          = เลขเอกสาร SO ของ DB ต้นทางนั้น
        จับคู่ 2 ฟิลด์นี้กับ DB ที่กำลังใช้งาน + เลข SO ที่ลูกค้าค้างชำระอยู่
        แล้วดูใบแจ้งหนี้ของใบสั่งขายฝั่งขนส่ง (ผูกผ่าน invoice_origin) ว่ายังค้างไหม

        อ่านผ่าน cursor ตรง ๆ ไม่ผ่าน ORM เพราะการเปิด registry ของอีก DB
        กินหน่วยความจำมาก และเราต้องการแค่ข้อมูลอ่านอย่างเดียว
        """ % TRANSPORT_DB
        if not so_names or self._cr.dbname == TRANSPORT_DB:
            return []
        cr = None
        rows = []
        try:
            cr = odoo.sql_db.db_connect(TRANSPORT_DB).cursor()
            # (1) ใบแจ้งหนี้ค่าขนส่งที่ลงบัญชีแล้วและยังค้างชำระ
            cr.execute("""
                SELECT DISTINCT
                       so.so_number        AS source_so,
                       so.name             AS transport_so,
                       am.name             AS invoice_name,
                       am.invoice_date     AS invoice_date,
                       am.invoice_date_due AS invoice_date_due,
                       am.amount_total     AS amount_total,
                       am.amount_residual  AS amount_residual,
                       am.payment_state    AS payment_state
                  FROM sale_order so
                  JOIN account_move am ON (am.invoice_origin = so.name
                                           OR am.id = so.shipping_invoice_id)
                 WHERE so.database_selection = %s
                   AND so.so_number IN %s
                   AND am.move_type = 'out_invoice'
                   AND am.state = 'posted'
                   AND am.amount_residual > 0
                   AND am.invoice_date >= %s
                 ORDER BY am.invoice_date
            """, (self._cr.dbname, tuple(so_names), DEBT_START_STR))
            for row in cr.dictfetchall():
                row['source_type'] = u'ใบแจ้งหนี้'
                rows.append(row)

            # (2) ยังไม่ออกใบแจ้งหนี้ หรือใบแจ้งหนี้ยังเป็นฉบับร่าง
            #     -> ดูยอดค่าขนส่งบนใบสั่งขายแทน (สูตรเดียวกับโมดูล
            #        custom_shipping_invoice ที่ใช้ตอนสร้างใบค่าขนส่ง)
            #        ค่าขนส่งเป็น 0 = ถือว่าไม่มีหนี้ ไม่ต้องขึ้นรายการ
            cr.execute("""
                SELECT so.so_number      AS source_so,
                       so.name           AS transport_so,
                       so.date_order::date AS invoice_date,
                       CASE WHEN so.use_special_delivery_zero
                                 AND COALESCE(so.shipping_cost_m, 0) = 0 THEN 0
                            WHEN COALESCE(so.shipping_cost_m, 0) > 0 THEN so.shipping_cost_m
                            ELSE COALESCE(so.shipping_cost, 0)
                       END               AS amount_residual,
                       (SELECT am2.name FROM account_move am2
                         WHERE (am2.invoice_origin = so.name
                                OR am2.id = so.shipping_invoice_id)
                           AND am2.move_type = 'out_invoice'
                           AND am2.state = 'draft'
                         ORDER BY am2.id DESC LIMIT 1) AS draft_invoice
                  FROM sale_order so
                 WHERE so.database_selection = %s
                   AND so.so_number IN %s
                   AND so.state IN ('sale', 'done')
                   AND so.date_order >= %s
                   AND NOT EXISTS (
                        SELECT 1 FROM account_move am
                         WHERE (am.invoice_origin = so.name
                                OR am.id = so.shipping_invoice_id)
                           AND am.move_type = 'out_invoice'
                           AND am.state = 'posted')
                 ORDER BY so.date_order
            """, (self._cr.dbname, tuple(so_names), DEBT_START_STR))
            for row in cr.dictfetchall():
                amount = row.get('amount_residual') or 0.0
                if amount <= 0:
                    continue          # ค่าขนส่ง 0 = ถือว่าชำระแล้ว
                draft = row.pop('draft_invoice', None)
                row.update({
                    'invoice_name': draft or '',
                    'invoice_date_due': False,
                    'amount_total': amount,
                    'payment_state': 'not_paid',
                    'source_type': (u'ใบแจ้งหนี้ฉบับร่าง' if draft
                                    else u'ยังไม่ออกใบแจ้งหนี้'),
                })
                rows.append(row)
            return rows
        except Exception:
            # หา DB ขนส่งไม่เจอ/ไม่มีฟิลด์ที่ใช้จับคู่ -> ข้ามไป อย่าให้ปุ่มอัพเดทล้ม
            _logger.exception(u'npd_debt_summary: อ่านค่าขนส่งจาก %s ไม่สำเร็จ',
                              TRANSPORT_DB)
            return []
        finally:
            if cr:
                cr.close()

    def _transport_source_so_names(self, commercial):
        """เลขเอกสาร SO ของลูกค้ารายนี้ ที่จะเอาไปจับคู่กับฝั่งขนส่ง

        ใช้ใบสั่งขายของลูกค้าตั้งแต่ปีที่กำหนด (DEBT_START_DATE) ทั้งหมด
        ไม่ได้จำกัดเฉพาะใบที่ยังค้างชำระฝั่งเรา เพราะค่าเช่ากับค่าขนส่ง
        เก็บเงินคนละใบ ลูกค้าจ่ายค่าเช่าครบแล้วแต่ยังค้างค่าขนส่งได้
        (ตรวจกับข้อมูลจริงแล้วเจอเคสนี้จริง) การกรองค้างชำระอยู่ที่ฝั่งขนส่ง
        คือเอาเฉพาะใบแจ้งหนี้ค่าขนส่งที่ amount_residual > 0
        """
        orders = self.env['sale.order'].search([
            ('partner_id', 'child_of', commercial.id),
            ('date_order', '>=', DEBT_START_STR),
        ])
        return set(name for name in orders.mapped('name') if name)

    def _populate_customer_data(self):
        """ดึงข้อมูลหนี้ทั้ง 4 ประเภทของลูกค้ารายนี้มาเก็บเป็น record จริง"""
        self.ensure_one()
        customer = self.customer_id
        if not customer:
            return
        today = date.today()
        commercial = customer.commercial_partner_id or customer

        # ====== 1) ใบแจ้งหนี้ แยกตามประเภท: ค่าเช่า / ค่าเช่าส่วนต่าง ======
        # (เก็บใบเดิมไว้ด้วย เพื่อแสดงสถานะ ค้าง/จ่ายแล้ว)
        # ใบค่าปรับหาย/ชำรุดไม่เข้าสองแท็บนี้ เพราะมีแท็บของตัวเองอยู่แล้ว
        # เก็บเฉพาะใบที่ยังค้างชำระ (ผู้ใช้ระบุ 21 ส.ค. 2026)
        # เดิมเก็บใบที่เคยเข้ารายการไว้ด้วยเพื่อโชว์สถานะ "จ่ายแล้ว"
        # แต่พอใช้จริงแท็บรกมาก (ตัวอย่าง 24 บรรทัด จ่ายแล้วไปตั้ง 21)
        # ยอดเงินไม่เคยรวมใบที่จ่ายแล้วอยู่แล้ว การตัดออกจึงไม่กระทบตัวเลข
        unpaid_invoices = self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('invoice_date', '>=', DEBT_START_STR),
        ])
        # กรองเฉพาะปี 2026 เป็นต้นไป (ใบเดิมที่เก็บไว้แต่เป็นปีเก่าจะถูกตัดออก = ล้างข้อมูลเก่า)
        invoices = unpaid_invoices.exists().filtered(
            lambda m: m.move_type == 'out_invoice'
            and m.invoice_date and m.invoice_date >= DEBT_START_DATE)
        inv_lines = [(5, 0, 0)]
        deposit_lines = [(5, 0, 0)]
        rentdiff_lines = [(5, 0, 0)]
        deposit_ids = self._deposit_invoice_ids(invoices)
        for inv in invoices:
            reason = self._move_reason_name(inv)
            if reason in (REASON_LOST, REASON_DAMAGE):
                continue
            line_vals = self._build_invoice_line_vals(inv, today)
            if inv.id in deposit_ids:
                # เช็คค่าประกันก่อนประเภท เพราะใบค่าประกันระบุประเภทเป็นค่าเช่า
                deposit_lines.append((0, 0, line_vals))
            elif reason == REASON_RENT_DIFF:
                rentdiff_lines.append((0, 0, line_vals))
            else:
                # ไม่ระบุประเภท = ค่าเช่า (ค่า default ของฟิลด์)
                inv_lines.append((0, 0, line_vals))

        # ============ 2) ค่าปรับหาย (เก็บใบเดิมไว้ด้วย) ============
        lost_reason = self.env['scrap.reason.code'].search([('name', '=', 'สินค้าหาย')], limit=1)
        penalty_lines = [(5, 0, 0)]
        total_penalty_residual = 0.0
        new_pen_ids = set(self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('reason_code_id', '=', lost_reason.id),
            ('invoice_date', '>=', DEBT_START_STR),
        ]).ids) if lost_reason else set()
        penalty_invoices = self.env['account.move'].browse(sorted(new_pen_ids)).exists().filtered(
            lambda m: m.invoice_date and m.invoice_date >= DEBT_START_DATE)
        if penalty_invoices:
            for pinv in penalty_invoices:
                pinv.invalidate_cache(['amount_residual'], [pinv.id])
                p_residual = pinv.amount_residual
                total_penalty_residual += p_residual
                branch_name = pinv.branch_id.name or '' if getattr(pinv, 'branch_id', False) else ''
                sales_name = pinv.sales_contact_id.name or '' if getattr(pinv, 'sales_contact_id', False) else ''
                rental_start, rental_end = self._get_rental_dates(pinv)
                penalty_amt = getattr(pinv, 'amount_price_subtotal_without_discount', 0.0) or 0.0
                if not penalty_amt:
                    penalty_amt = sum(
                        l.quantity * l.price_unit for l in pinv.invoice_line_ids
                        if not l.exclude_from_invoice_tab)
                discount_amt = (getattr(pinv, 'discount_amt_line', 0.0) or 0.0)
                discount_amt += (getattr(pinv, 'discount_amt', 0.0) or 0.0)
                net_penalty = pinv.amount_total
                amount_paid = pinv.amount_total - p_residual
                product_html, product_line_vals = self._build_product_html_and_lines(pinv)
                penalty_lines.append((0, 0, {
                    'invoice_id': pinv.id,
                    'invoice_name': pinv.name,
                    'branch_name': branch_name,
                    'sales_contact_name': sales_name,
                    'rental_start_date': pinv.invoice_date,
                    'rental_end_date': pinv.invoice_date_due,
                    'penalty_amount': penalty_amt,
                    'discount_amount': discount_amt,
                    'net_penalty': net_penalty,
                    'amount_paid': amount_paid,
                    'amount_residual': p_residual,
                    'product_info_html': product_html,
                    'penalty_product_line_ids': product_line_vals,
                }))

        # ============ 3) ค่าปรับชำรุด (เก็บใบเดิมไว้ด้วย) ============
        damage_reason = self.env['scrap.reason.code'].search([('name', '=', 'สินค้าชำรุด')], limit=1)
        damage_lines = [(5, 0, 0)]
        total_damage_residual = 0.0
        new_dmg_ids = set(self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('reason_code_id', '=', damage_reason.id),
            ('invoice_date', '>=', DEBT_START_STR),
        ]).ids) if damage_reason else set()
        damage_invoices = self.env['account.move'].browse(sorted(new_dmg_ids)).exists().filtered(
            lambda m: m.invoice_date and m.invoice_date >= DEBT_START_DATE)
        if damage_invoices:
            for dinv in damage_invoices:
                dinv.invalidate_cache(['amount_residual'], [dinv.id])
                d_residual = dinv.amount_residual
                total_damage_residual += d_residual
                d_branch_name = dinv.branch_id.name or '' if getattr(dinv, 'branch_id', False) else ''
                d_sales_name = dinv.sales_contact_id.name or '' if getattr(dinv, 'sales_contact_id', False) else ''
                d_rental_start, d_rental_end = self._get_rental_dates(dinv)
                d_penalty_amt = getattr(dinv, 'amount_price_subtotal_without_discount', 0.0) or 0.0
                if not d_penalty_amt:
                    d_penalty_amt = sum(
                        l.quantity * l.price_unit for l in dinv.invoice_line_ids
                        if not l.exclude_from_invoice_tab)
                d_discount_amt = (getattr(dinv, 'discount_amt_line', 0.0) or 0.0)
                d_discount_amt += (getattr(dinv, 'discount_amt', 0.0) or 0.0)
                d_net_penalty = dinv.amount_total
                d_amount_paid = dinv.amount_total - d_residual
                d_product_html = self._build_product_html(dinv)
                damage_lines.append((0, 0, {
                    'invoice_id': dinv.id,
                    'invoice_name': dinv.name,
                    'branch_name': d_branch_name,
                    'sales_contact_name': d_sales_name,
                    'rental_start_date': dinv.invoice_date,
                    'rental_end_date': dinv.invoice_date_due,
                    'damage_amount': d_penalty_amt,
                    'discount_amount': d_discount_amt,
                    'net_damage': d_net_penalty,
                    'amount_paid': d_amount_paid,
                    'amount_residual': d_residual,
                    'product_info_html': d_product_html,
                }))

        # ============ 4) ค่า Tax (ภาษีหัก ณ ที่จ่าย) ============
        tax_lines = [(5, 0, 0)]
        total_tax_amount = 0.0
        seen_tax_pairs = set()

        candidate_invoices = self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', DEBT_START_STR),
        ])
        for tinv in candidate_invoices:
            payment_inv_lines = self.env['account.payment.invoice'].search([
                ('invoice_id', '=', tinv.id),
                ('payment_id.state', '=', 'posted'),
            ])
            for pi_line in payment_inv_lines:
                payment = pi_line.payment_id
                if not payment:
                    continue
                if not getattr(payment, 'wht_has_slip', False):
                    continue
                pair_key = (tinv.id, payment.id)
                # วิธี A: หาจาก paid_ids (payment method ชื่อ "ภาษี...หัก...")
                for paid_line in payment.paid_ids:
                    method_name = (paid_line.payment_method_id.name or '').strip() if paid_line.payment_method_id else ''
                    if method_name and 'ภาษี' in method_name and 'หัก' in method_name:
                        if pair_key in seen_tax_pairs:
                            continue
                        seen_tax_pairs.add(pair_key)
                        tax_amt = paid_line.total or 0.0
                        total_tax_amount += tax_amt
                        tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv, payment, tax_amt)))
                # วิธี B: หาจาก wt_cert_ids (หนังสือรับรองหัก ณ ที่จ่าย)
                for wht_cert in payment.wt_cert_ids:
                    if pair_key in seen_tax_pairs:
                        continue
                    wht_amt = wht_cert.tax_amount or 0.0
                    if wht_amt > 0:
                        seen_tax_pairs.add(pair_key)
                        total_tax_amount += wht_amt
                        tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv, payment, wht_amt)))

        # ============ 5) ค่าขนส่ง (ข้ามไปดูที่ DB ของบริษัทขนส่ง) ============
        transport_lines = [(5, 0, 0)]
        so_names = self._transport_source_so_names(commercial)
        for row in self._transport_debt_rows(sorted(so_names)):
            residual = row['amount_residual'] or 0.0
            due = row['invoice_date_due']
            transport_lines.append((0, 0, {
                'source_type': row.get('source_type') or '',
                'source_so': row['source_so'] or '',
                'transport_so': row['transport_so'] or '',
                'invoice_name': row['invoice_name'] or '',
                'invoice_date': row['invoice_date'],
                'invoice_date_due': due,
                'amount_total': row['amount_total'] or 0.0,
                'amount_residual': residual,
                'payment_state': row['payment_state'] or '',
                'days_overdue': (today - due).days if due else 0,
            }))

        # ============ เขียนข้อมูลทั้งหมดลง record ============
        self.write({
            'partner_name': customer.name or '',
            'partner_phone': customer.phone or '',
            'partner_mobile': customer.mobile or '',
            'partner_email': customer.email or '',
            'partner_vat': customer.vat or '',
            'partner_street': customer.street or '',
            'partner_street2': customer.street2 or '',
            'partner_city': customer.city or '',
            'partner_state_id': customer.state_id.id if customer.state_id else False,
            'partner_zip': customer.zip or '',
            'customer_invoice_line_ids': inv_lines,
            'customer_deposit_line_ids': deposit_lines,
            'customer_rentdiff_line_ids': rentdiff_lines,
            'customer_penalty_line_ids': penalty_lines,
            'customer_damage_line_ids': damage_lines,
            'customer_transport_line_ids': transport_lines,
            'customer_tax_line_ids': tax_lines,
            'last_update': fields.Datetime.now(),
        })

    # ------------------------------------------------------------------ helpers
    def _get_rental_dates(self, inv):
        """ดึงวันเริ่มเช่า/วันคืน จาก stock.picking ที่อ้างอิงเอกสารนี้"""
        rental_start = False
        rental_end = False
        if inv.invoice_origin:
            picking = self.env['stock.picking'].search([
                ('origin', '=', inv.invoice_origin)], limit=1, order='id desc')
            if not picking:
                picking = self.env['stock.picking'].search([
                    ('name', '=', inv.invoice_origin)], limit=1)
            if picking:
                rental_start = picking.start_x_date if hasattr(picking, 'start_x_date') else False
                rental_end = picking.end_x_date if hasattr(picking, 'end_x_date') else False
        return rental_start, rental_end

    def _build_product_html(self, inv):
        """สร้าง HTML table แสดงรายการสินค้าของใบแจ้งหนี้"""
        html = '<table class="table table-sm table-bordered" style="width:100%">'
        html += '<thead><tr style="background:#f5f5f5">'
        html += '<th>สินค้า</th><th>รายละเอียด</th>'
        html += '<th style="text-align:right">จำนวน</th>'
        html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
        html += '<th style="text-align:right">ส่วนลด (%)</th>'
        html += '<th style="text-align:right">ยอดรวม</th>'
        html += '</tr></thead><tbody>'
        has_lines = False
        for line in inv.invoice_line_ids:
            if line.exclude_from_invoice_tab:
                continue
            has_lines = True
            pname = line.product_id.name if line.product_id else ''
            html += '<tr>'
            html += '<td>%s</td>' % pname
            html += '<td>%s</td>' % (line.name or '')
            html += '<td style="text-align:right">%.2f</td>' % line.quantity
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_unit)
            html += '<td style="text-align:right">%.2f</td>' % line.discount
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_subtotal)
            html += '</tr>'
        if not has_lines:
            html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
        html += '</tbody></table>'
        return html

    def _build_product_html_and_lines(self, inv):
        """สร้าง HTML table + product line vals (สำหรับค่าปรับหาย)"""
        html = '<table class="table table-sm table-bordered" style="width:100%">'
        html += '<thead><tr style="background:#f5f5f5">'
        html += '<th>สินค้า</th><th>รายละเอียด</th>'
        html += '<th style="text-align:right">จำนวน</th>'
        html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
        html += '<th style="text-align:right">ส่วนลด (%)</th>'
        html += '<th style="text-align:right">ยอดรวม</th>'
        html += '</tr></thead><tbody>'
        has_lines = False
        product_line_vals = []
        for line in inv.invoice_line_ids:
            if line.exclude_from_invoice_tab:
                continue
            has_lines = True
            pname = line.product_id.name if line.product_id else ''
            html += '<tr>'
            html += '<td>%s</td>' % pname
            html += '<td>%s</td>' % (line.name or '')
            html += '<td style="text-align:right">%.2f</td>' % line.quantity
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_unit)
            html += '<td style="text-align:right">%.2f</td>' % line.discount
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_subtotal)
            html += '</tr>'
            product_line_vals.append((0, 0, {
                'product_name': pname,
                'description': line.name or '',
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'price_subtotal': line.price_subtotal,
            }))
        if not has_lines:
            html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
        html += '</tbody></table>'
        return html, product_line_vals

    def _prepare_tax_line_vals(self, invoice, payment, tax_amt):
        """สร้าง dict สำหรับ tax line record"""
        return {
            'invoice_id': invoice.id,
            'invoice_name': invoice.name,
            'invoice_origin': invoice.invoice_origin or '',
            'invoice_date': invoice.invoice_date,
            'invoice_date_due': invoice.invoice_date_due,
            'amount_total': invoice.amount_total,
            'payment_id': payment.id,
            'payment_name': payment.name or '',
            'tax_amount': tax_amt,
            'product_info_html': self._build_product_html(invoice),
        }


class NpdDebtSummaryInvoiceLine(models.Model):
    _name = 'npd.debt.summary.invoice.line'
    _inherit = ['npd.debt.collection.status.mixin']
    _description = 'รายการใบแจ้งหนี้ค้างชำระ (สรุปหนี้)'
    _order = 'invoice_date_due asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้', related='invoice_id.name', store=True, readonly=True)
    invoice_origin = fields.Char(string='อ้างอิง SO')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='รวม', digits=(16, 2))
    amount_residual = fields.Float(string='ยอดเงินค้างชำระ', digits=(16, 2))
    payment_state = fields.Char(string='สถานะ (code)')
    payment_state_label = fields.Char(string='สถานะการชำระเงิน')
    days_overdue = fields.Integer(string='จำนวนวันที่เกิน')
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้ค้างชำระ'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryDepositLine(models.Model):
    """บรรทัดแท็บ 'ใบแจ้งหนี้ค่าประกัน' (โครงเดียวกับแท็บใบแจ้งหนี้ค่าเช่า)"""
    _name = 'npd.debt.summary.deposit.line'
    _inherit = ['npd.debt.collection.status.mixin']
    _description = 'รายการใบแจ้งหนี้ค่าประกัน (สรุปหนี้)'
    _order = 'invoice_date_due asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้', related='invoice_id.name', store=True, readonly=True)
    invoice_origin = fields.Char(string='อ้างอิง SO')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='รวม', digits=(16, 2))
    amount_residual = fields.Float(string='ยอดเงินค้างชำระ', digits=(16, 2))
    payment_state = fields.Char(string='สถานะ (code)')
    payment_state_label = fields.Char(string='สถานะการชำระเงิน')
    days_overdue = fields.Integer(string='จำนวนวันที่เกิน')
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้ค่าประกัน'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryRentDiffLine(models.Model):
    """บรรทัดแท็บ 'ค่าเช่าส่วนต่าง'

    โครงเหมือนแท็บใบแจ้งหนี้ค่าเช่าทุกช่อง ต่างกันแค่ประเภทของใบแจ้งหนี้
    ที่ดึงเข้ามา (scrap.reason.code = ค่าเช่าส่วนต่าง)
    """
    _name = 'npd.debt.summary.rentdiff.line'
    _inherit = ['npd.debt.collection.status.mixin']
    _description = 'รายการค่าเช่าส่วนต่าง (สรุปหนี้)'
    _order = 'invoice_date_due asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้', related='invoice_id.name', store=True, readonly=True)
    invoice_origin = fields.Char(string='อ้างอิง SO')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='รวม', digits=(16, 2))
    amount_residual = fields.Float(string='ยอดเงินค้างชำระ', digits=(16, 2))
    payment_state = fields.Char(string='สถานะ (code)')
    payment_state_label = fields.Char(string='สถานะการชำระเงิน')
    days_overdue = fields.Integer(string='จำนวนวันที่เกิน')
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ค่าเช่าส่วนต่าง'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryPenaltyLine(models.Model):
    _name = 'npd.debt.summary.penalty.line'
    _inherit = ['npd.debt.collection.status.mixin']
    _collection_date_field = 'rental_start_date'
    _description = 'รายการค่าปรับหาย (สรุปหนี้)'
    _order = 'invoice_name asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขเอกสาร', related='invoice_id.name', store=True, readonly=True)
    branch_name = fields.Char(string='สาขา')
    sales_contact_name = fields.Char(string='เซลล์')
    rental_start_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    rental_end_date = fields.Date(string='วันกำหนดจ่าย')
    penalty_amount = fields.Float(string='ค่าปรับหาย', digits=(16, 2))
    discount_amount = fields.Float(string='ส่วนลด', digits=(16, 2))
    net_penalty = fields.Float(string='ปรับหายสุทธิ', digits=(16, 2))
    amount_paid = fields.Float(string='รับชำระ', digits=(16, 2))
    amount_residual = fields.Float(string='คงเหลือ', digits=(16, 2))
    penalty_product_line_ids = fields.One2many(
        'npd.debt.summary.penalty.product.line', 'penalty_line_id', string='รายการสินค้า')
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้ค่าปรับหาย'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryPenaltyProductLine(models.Model):
    _name = 'npd.debt.summary.penalty.product.line'
    _description = 'รายการสินค้าค่าปรับหาย (สรุปหนี้)'

    penalty_line_id = fields.Many2one('npd.debt.summary.penalty.line', string='รายการค่าปรับหาย', ondelete='cascade')
    product_name = fields.Char(string='สินค้า')
    description = fields.Char(string='รายละเอียด')
    quantity = fields.Float(string='จำนวน', digits=(16, 2))
    price_unit = fields.Float(string='ราคาต่อหน่วย', digits=(16, 2))
    discount = fields.Float(string='ส่วนลด (%)', digits=(16, 2))
    price_subtotal = fields.Float(string='ยอดรวม', digits=(16, 2))


class NpdDebtSummaryDamageLine(models.Model):
    _name = 'npd.debt.summary.damage.line'
    _inherit = ['npd.debt.collection.status.mixin']
    _collection_date_field = 'rental_start_date'
    _description = 'รายการค่าปรับชำรุด (สรุปหนี้)'
    _order = 'invoice_name asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขเอกสาร', related='invoice_id.name', store=True, readonly=True)
    branch_name = fields.Char(string='สาขา')
    sales_contact_name = fields.Char(string='เซลล์')
    rental_start_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    rental_end_date = fields.Date(string='วันกำหนดจ่าย')
    damage_amount = fields.Float(string='ค่าปรับชำรุด', digits=(16, 2))
    discount_amount = fields.Float(string='ส่วนลด', digits=(16, 2))
    net_damage = fields.Float(string='ปรับชำรุดสุทธิ', digits=(16, 2))
    amount_paid = fields.Float(string='รับชำระ', digits=(16, 2))
    amount_residual = fields.Float(string='คงเหลือ', digits=(16, 2))
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้ค่าปรับชำรุด'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryTransportLine(models.Model):
    """บรรทัดแท็บ 'ค่าขนส่ง'

    ข้อมูลมาจากอีกฐานข้อมูล (บริษัทขนส่ง) จึงเก็บเป็นข้อความล้วน ไม่มี
    many2one ชี้ไปที่ account.move เหมือนแท็บอื่น และไม่มีปุ่มเปิดใบแจ้งหนี้
    """
    _name = 'npd.debt.summary.transport.line'
    _inherit = ['npd.debt.collection.status.mixin']
    _description = 'รายการค่าขนส่ง (สรุปหนี้)'
    _order = 'invoice_date_due asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    source_so = fields.Char(string='เลขเอกสาร SO')
    transport_so = fields.Char(string='ใบสั่งขายฝั่งขนส่ง')
    source_type = fields.Char(string='ที่มา',
        help='ใบแจ้งหนี้ / ใบแจ้งหนี้ฉบับร่าง / ยังไม่ออกใบแจ้งหนี้ '
             '(สองแบบหลังใช้ยอดค่าขนส่งบนใบสั่งขายฝั่งขนส่ง)')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='รวม', digits=(16, 2))
    amount_residual = fields.Float(string='ยอดเงินค้างชำระ', digits=(16, 2))
    payment_state = fields.Char(string='สถานะ (code)')
    days_overdue = fields.Integer(string='จำนวนวันที่เกิน')
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'


class NpdDebtSummaryTaxLine(models.Model):
    _name = 'npd.debt.summary.tax.line'
    _inherit = ['npd.debt.collection.status.mixin']
    _description = 'รายการค่าหัก ณ ที่จ่าย (สรุปหนี้)'
    _order = 'invoice_name asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้', related='invoice_id.name', store=True, readonly=True)
    invoice_origin = fields.Char(string='อ้างอิง SO')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='ยอดรวมใบแจ้งหนี้', digits=(16, 2))
    payment_id = fields.Many2one('account.payment', string='รับชำระ')
    payment_name = fields.Char(string='เลขที่รับชำระ')
    tax_amount = fields.Float(string='ยอด Tax', digits=(16, 2))
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('invoice_id.amount_residual')
    def _compute_payment_status(self):
        for l in self:
            resid = l.invoice_id.amount_residual if l.invoice_id else 0.0
            l.payment_status = 'paid' if (resid or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
