# -*- coding: utf-8 -*-
import logging

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
    def sync_from_period(self, period):
        """สร้าง/อัพเดทบรรทัด ภ.ง.ด.1 ประเภท 'system' จากรายการเงินเดือนในรอบนี้

        - แยกตามบริษัทของพนักงานแต่ละคน (company จาก employee.salary)
        - เงินได้ = net_salary (เงินสุทธิ), ภาษี = tax_monthly, วันที่ = payment_date
        - ลบบรรทัด system เดิมของรอบนี้แล้วสร้างใหม่ เพื่อไม่ให้มีข้อมูลค้าง/ซ้ำ
        - ไม่ยุ่งกับบรรทัดที่นำเข้าจาก excel
        คืนค่า: จำนวนบรรทัดที่สร้าง
        """
        period = period or self
        created = 0
        for prd in period:
            # ลบของเดิม (เฉพาะ system) ของรอบนี้ทิ้งก่อน
            self.search([
                ('period_id', '=', prd.id),
                ('source_type', '=', 'system'),
            ]).unlink()

            vals_list = []
            skipped = []
            for payroll in prd.payroll_ids:
                emp = payroll.employee_id
                if not emp:
                    continue
                # ต้องมีบริษัท มิฉะนั้นจะไม่แสดงในเมนูบริษัทใด และ company เป็น required
                if not emp.company:
                    skipped.append(emp.display_name)
                    continue
                prefix = emp.prefix_th or ''
                firstname = emp.firstname or ''
                lastname = emp.lastname or ''
                full_name = ("%s%s %s" % (prefix, firstname, lastname)).strip()
                vals_list.append({
                    'company': emp.company,
                    'id_card_number': emp.id_card_number or '',
                    'full_name': full_name,
                    'pay_date': payroll.payment_date,
                    'income': payroll.net_salary or 0.0,       # เงินสุทธิ
                    'tax': payroll.tax_monthly or 0.0,          # ภาษีหัก ณ ที่จ่าย/เดือน (ที่ใช้)
                    'source_type': 'system',
                    'employee_id': emp.id,
                    'payroll_id': payroll.id,
                    'period_id': prd.id,
                })
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
