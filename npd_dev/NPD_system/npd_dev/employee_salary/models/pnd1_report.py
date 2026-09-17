# -*- coding: utf-8 -*-
import calendar
import logging
import re
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Pnd1Line(models.Model):
    """รายงาน ภ.ง.ด.1 — บรรทัดข้อมูลภาษีหัก ณ ที่จ่าย รายเดือน แยกตามบริษัท

    ข้อมูลมี 2 แหล่ง (source_type):
      - excel  : ผู้ใช้นำเข้า/กรอกเอง (แก้ไขได้)
      - system : ดึงจากในระบบ payroll.salary ผ่านรอบทำเงินเดือน (แก้ไขไม่ได้)
    """
    _name = "pnd1.line"
    _description = "รายงาน ภ.ง.ด.1"
    _order = "pay_date desc, id desc"

    # บริษัทเดียวกับ employee.salary.HRMS_COMPANY (คีย์ต้องตรงกันเพื่อให้ domain ของเมนูกรองได้)
    HRMS_COMPANY = [
        ("นภดลเอสกรุ๊ปจำกัด", "นภดลเอสกรุ๊ปจำกัด"),
        ("เอ็นพีดีสตีลเทคจำกัด", "เอ็นพีดีสตีลเทคจำกัด"),
        ("เอ็นพีดีโลจิสติกส์จำกัด", "เอ็นพีดีโลจิสติกส์จำกัด"),
        ("นภดลกรุงเทพจำกัด", "นภดลกรุงเทพจำกัด"),
        ("นภดลอินเตอร์เทรดดิ้งจำกัด", "นภดลอินเตอร์เทรดดิ้งจำกัด"),
    ]

    company = fields.Selection(
        selection=HRMS_COMPANY, string="บริษัท", required=True, index=True)
    id_card_number = fields.Char(string="เลขบัตรประจำตัวประชาชน")
    full_name = fields.Char(string="ชื่อ-นามสกุล")
    pay_date = fields.Date(string="วัน/เดือน/ปี")
    income = fields.Float(string="จำนวนเงินได้")
    tax = fields.Float(string="ภาษีที่ต้องหัก")
    source_type = fields.Selection([
        ('excel', 'เข้าผ่าน excel'),
        ('system', 'ดึงจากในระบบ'),
    ], string="ประเภทการลงข้อมูล", default='excel', required=True, index=True)

    # ── ความเชื่อมโยงกับระบบ (เฉพาะ source_type='system') ──
    employee_id = fields.Many2one('employee.salary', string="พนักงาน", ondelete='set null')
    payroll_id = fields.Many2one('payroll.salary', string="รายการเงินเดือน", ondelete='cascade')
    period_id = fields.Many2one('payroll.period', string="รอบทำเงินเดือน", ondelete='cascade')

    @api.model
    def _normalize_pay_date(self, value):
        """วันที่ที่พิมพ์ปี พ.ศ. ลงช่องวันที่ของ Excel (เช่น 2569-01-28) → ปี ค.ศ.
        ถ้าไม่แปลง ระบบจะมองเป็นปีอนาคต ทำให้เรียงลำดับ/กรองตามปีผิด"""
        d = fields.Date.to_date(value)
        if not d or d.year < 2500:
            return value
        year = d.year - 543
        return date(year, d.month, min(d.day, calendar.monthrange(year, d.month)[1]))

    @api.model
    def _normalize_taxid(self, taxid):
        """เลขบัตรสำหรับจับคู่: เอาเฉพาะตัวเลข แล้วตัด 0 นำหน้า"""
        return re.sub(r"\D", "", taxid or "").lstrip("0")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('pay_date'):
                vals['pay_date'] = self._normalize_pay_date(vals['pay_date'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('pay_date'):
            vals['pay_date'] = self._normalize_pay_date(vals['pay_date'])
        return super().write(vals)

    @api.model
    def _system_pay_date(self, payroll):
        """วันที่ของแถว ภ.ง.ด.1 — ใช้วันจ่ายของเงินเดือนถ้าตรงเดือน/ปีของเงินเดือนนั้น
        ไม่งั้น (เช่น ทำเงินเดือนนอกรอบ วันจ่ายติดค่า default เป็นเดือนที่กดสร้าง)
        ใช้วันที่ 28 ของเดือนเงินเดือน"""
        pay = payroll.payment_date
        try:
            year, month = int(payroll.year), int(payroll.month)
        except (TypeError, ValueError):
            return pay
        if pay and pay.year == year and pay.month == month:
            return pay
        return date(year, month, min(28, calendar.monthrange(year, month)[1]))

    @api.model
    def _prepare_system_vals(self, payroll, company):
        emp = payroll.employee_id
        full_name = ("%s%s %s" % (
            emp.prefix_th or '', emp.firstname or '', emp.lastname or '')).strip()
        return {
            'company': company,
            'id_card_number': emp.id_card_number or '',
            'full_name': full_name,
            'pay_date': self._system_pay_date(payroll),
            # ฝ่ายบัญชี: เงินได้ใน ภ.ง.ด.1 = รายรับ (รวมรายได้ก่อนหักรายการหัก) ไม่ใช่เงินสุทธิ
            'income': payroll.total_gross or 0.0,
            'tax': payroll.tax_monthly or 0.0,          # ภาษีหัก ณ ที่จ่าย/เดือน (ที่ใช้)
            'source_type': 'system',
            'employee_id': emp.id,
            'payroll_id': payroll.id,
            'period_id': payroll.period_id.id or False,
        }

    @api.model
    def sync_from_period(self, period):
        """สร้าง/อัพเดทบรรทัด ภ.ง.ด.1 ประเภท 'system' จากรายการเงินเดือนในรอบนี้

        - แยกตามบริษัทของพนักงานแต่ละคน (company จาก employee.salary)
        - เงินได้ = total_gross (รวมรายได้ ก่อนหักรายการหัก), ภาษี = tax_monthly, วันที่ = payment_date
        - ลบบรรทัด system เดิมของรอบนี้แล้วสร้างใหม่ เพื่อไม่ให้มีข้อมูลค้าง/ซ้ำ
        - ไม่ยุ่งกับบรรทัดที่นำเข้าจาก excel
        คืนค่า: จำนวนบรรทัดที่สร้าง
        """
        period = period or self
        created = 0
        for prd in period:
            # ลบของเดิม (เฉพาะ system) ของรอบนี้ทิ้งก่อน — แต่จำบริษัทของแต่ละรายการไว้
            # พนักงานที่ย้ายบริษัทภายหลังต้องไม่ถูกย้ายข้อมูลเดือนเก่าไปบริษัทใหม่
            existing = self.search([
                ('period_id', '=', prd.id),
                ('source_type', '=', 'system'),
            ])
            company_by_payroll = {
                line.payroll_id.id: line.company for line in existing if line.payroll_id}
            existing.unlink()

            vals_list = []
            skipped = []
            for payroll in prd.payroll_ids:
                emp = payroll.employee_id
                if not emp:
                    continue
                company = company_by_payroll.get(payroll.id) or emp.company
                # ต้องมีบริษัท มิฉะนั้นจะไม่แสดงในเมนูบริษัทใด และ company เป็น required
                if not company:
                    skipped.append(emp.display_name)
                    continue
                vals = self._prepare_system_vals(payroll, company)
                vals['period_id'] = prd.id
                vals_list.append(vals)
            if vals_list:
                self.create(vals_list)
                created += len(vals_list)
            if skipped:
                _logger.warning(
                    "[PND1] ข้ามพนักงานที่ไม่มีบริษัท %d คน: %s",
                    len(skipped), ", ".join(skipped))
            _logger.info("[PND1] sync period %s → สร้าง %d บรรทัด", prd.display_name, len(vals_list))
        # เติมชื่อจากระบบให้แถว excel ที่เลขบัตรตรงกัน (ทำครั้งเดียวแบบ global)
        self._apply_system_names_to_excel()
        return created

    @api.model
    def reconcile_system_lines(self):
        """ให้แถว ภ.ง.ด.1 (system) ตามทันรายการเงินเดือนล่าสุด — รันทุกวันจาก cron
        และหลังกด "อัพเดตข้อมูลเงินเดือน"

        ครอบเฉพาะเดือนที่ทำเงินเดือนด้วยระบบแล้ว (มีรอบที่ไม่ใช่ร่าง) — เดือนก่อนหน้านั้น
        ยึดข้อมูลที่นำเข้าจาก excel (เงินเดือนที่ทำไว้ก่อนเริ่มใช้ระบบเป็นรายการทดลอง)
        - แก้เงินเดือนหลังดึงไปแล้ว → อัพเดตเงินได้/ภาษี โดยคงบริษัทเดิมของเดือนนั้น
        - เงินเดือนที่ยังไม่มีแถว (เช่น ทำนอกรอบ) → สร้างแถวให้ บริษัท = สังกัดปัจจุบัน
          แล้วลบแถว excel ของคนเดียวกัน บริษัทเดียวกัน เดือนเดียวกัน (ใช้ข้อมูลระบบแทน)
        คืนค่า dict จำนวนที่อัพเดต/สร้าง/ลบ
        """
        result = {'updated': 0, 'created': 0, 'excel_removed': 0}
        months = {
            (p.year, p.month)
            for p in self.env['payroll.period'].search([('state', '!=', 'draft')])
        }
        if not months:
            return result
        domain = ['|'] * (len(months) - 1)
        for year, month in sorted(months):
            domain += ['&', ('year', '=', year), ('month', '=', month)]
        payrolls = self.env['payroll.salary'].search(domain)

        line_by_payroll = {}
        for line in self.search([('source_type', '=', 'system'),
                                 ('payroll_id', 'in', payrolls.ids)]):
            line_by_payroll.setdefault(line.payroll_id.id, line)

        new_vals = []
        for payroll in payrolls:
            emp = payroll.employee_id
            if not emp:
                continue
            income = payroll.total_gross or 0.0
            tax = payroll.tax_monthly or 0.0
            line = line_by_payroll.get(payroll.id)
            if line:
                if abs((line.income or 0.0) - income) > 0.005 or abs((line.tax or 0.0) - tax) > 0.005:
                    line.write({'income': income, 'tax': tax})
                    result['updated'] += 1
            elif emp.company:
                new_vals.append(self._prepare_system_vals(payroll, emp.company))

        if new_vals:
            created = self.create(new_vals)
            result['created'] = len(created)
            result['excel_removed'] = self._remove_excel_overlaps(created)
        if any(result.values()):
            _logger.info("[PND1] reconcile: อัพเดต %(updated)d, สร้าง %(created)d, "
                         "ลบแถว excel ที่ซ้ำ %(excel_removed)d", result)
        return result

    @api.model
    def _remove_excel_overlaps(self, system_lines):
        """ลบแถว excel ที่ซ้ำกับแถวระบบ (คนเดียวกัน บริษัทเดียวกัน เดือนเดียวกัน)"""
        to_remove = self.browse()
        for line in system_lines:
            taxid = self._normalize_taxid(line.id_card_number)
            if not line.pay_date or not taxid:
                continue
            year, month = line.pay_date.year, line.pay_date.month
            last_day = calendar.monthrange(year, month)[1]
            # เผื่อแถวเก่าที่ยังเก็บปี พ.ศ.
            candidates = self.search([
                ('source_type', '=', 'excel'),
                ('company', '=', line.company),
                '|',
                '&', ('pay_date', '>=', date(year, month, 1)),
                     ('pay_date', '<=', date(year, month, last_day)),
                '&', ('pay_date', '>=', date(year + 543, month, 1)),
                     ('pay_date', '<=', date(year + 543, month, last_day)),
            ])
            to_remove |= candidates.filtered(
                lambda l: self._normalize_taxid(l.id_card_number) == taxid)
        count = len(to_remove)
        to_remove.unlink()
        return count

    @api.model
    def _apply_system_names_to_excel(self):
        """ใช้ชื่อจากระบบแทนชื่อพิมพ์เองในแถว 'เข้าผ่าน excel' เมื่อเลขบัตรตรงกัน

        ชื่อที่นำเข้าจาก excel เป็นข้อความพิมพ์เอง รูปแบบมักไม่ตรงกับในระบบ
        → ถ้าเลขบัตรตรงกับพนักงานในระบบ (แถว source_type='system') ให้ทับด้วยชื่อจากระบบ
        เพื่อให้ชื่อสม่ำเสมอก่อนนำไปออกหนังสือรับรองหัก ณ ที่จ่าย (hr.withholding.tax.cert)
        อัพเดตผ่าน SQL เพื่อความเร็ว แล้ว invalidate cache ให้ ORM เห็นค่าล่าสุด
        คืนค่า: จำนวนบรรทัดที่ถูกแก้ชื่อ
        """
        # ให้ค่าที่เพิ่งสร้าง/แก้ผ่าน ORM ลง DB ก่อน แล้ว SQL จะเห็นข้อมูลล่าสุด
        self.env['pnd1.line'].flush(['source_type', 'id_card_number', 'full_name'])
        self.env.cr.execute("""
            UPDATE pnd1_line AS e
               SET full_name = s.full_name
              FROM (
                    SELECT DISTINCT ON (btrim(id_card_number))
                           btrim(id_card_number) AS id_card,
                           full_name
                      FROM pnd1_line
                     WHERE source_type = 'system'
                       AND btrim(COALESCE(id_card_number, '')) <> ''
                       AND btrim(COALESCE(full_name, '')) <> ''
                     ORDER BY btrim(id_card_number), id DESC
                   ) AS s
             WHERE e.source_type = 'excel'
               AND btrim(COALESCE(e.id_card_number, '')) = s.id_card
               AND COALESCE(e.full_name, '') <> s.full_name
        """)
        updated = self.env.cr.rowcount
        if updated:
            self.env['pnd1.line'].invalidate_cache(['full_name'])
            _logger.info("[PND1] เติมชื่อจากระบบให้แถว excel %d บรรทัด", updated)
        return updated
