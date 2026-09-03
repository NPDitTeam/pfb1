from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

INCOME_TAX_FORM = [
    ("pnd1", "PND1"),
    ("pnd1a", "PND1a"),
    ("pnd3", "PND3"),
    ("pnd3a", "PND3a"),
    ("pnd53", "PND53"),
]

WHT_CERT_INCOME_TYPE = [
    ("1", "1. เงินเดือน ค่าจ้าง เบี้ยเลี้ยง โบนัส ฯลฯ 40(1)"),
    ("2", "2. ค่าธรรมเนียม ค่านายหน้า ฯลฯ 40(2)"),
    ("3", "3. ค่าแห่งลิขสิทธิ์ ฯลฯ 40(3)"),
    ("5", "5. ค่าจ้างทำของ ค่าบริการ ค่าเช่า ค่าขนส่ง ฯลฯ 40(7)(8)"),
    ("6", "6. อื่นๆ (ระบุ)"),
]

TAX_PAYER = [
    ("withholding", "Withholding"),
    ("paid_one_time", "Paid One Time"),
]


class HRWithholdingTaxCert(models.Model):
    _name = "hr.withholding.tax.cert"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "HR Withholding Tax Certificate"
    _order = "date desc, id desc"
    _sql_constraints = [
        (
            "employee_year_unique",
            "UNIQUE(employee_id, report_year)",
            "มี WT Certificate ของพนักงานคนนี้ในปีนี้แล้ว!",
        ),
    ]

    name = fields.Char(
        string="Number",
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=fields.Date.context_today,
        tracking=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")],
        default="draft",
        copy=False,
        tracking=True,
    )
    report_year = fields.Char(
        string="ปี (พ.ศ./ค.ศ.)",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=lambda self: str(fields.Date.context_today(self).year),
        help="ปีที่ต้องการรวมเงินสุทธิ เช่น 2025 หรือ 2568",
        tracking=True,
    )
    total_net_salary = fields.Float(
        string="เงินได้รวมทั้งปี (จาก ภ.ง.ด.1)",
        compute="_compute_total_net_salary",
        readonly=True,
        help="รวมยอด 'จำนวนเงินได้' จากรายงาน ภ.ง.ด.1 ของเลขบัตรนี้ในปีที่ระบุ",
    )
    total_tax = fields.Float(
        string="ภาษีรวมทั้งปี (จาก ภ.ง.ด.1)",
        compute="_compute_total_net_salary",
        readonly=True,
        help="รวมยอด 'ภาษีที่ต้องหัก' จากรายงาน ภ.ง.ด.1 ของเลขบัตรนี้ในปีที่ระบุ",
    )
    sso_amount = fields.Float(
        string="กองทุนประกันสังคม (ทั้งปี)",
        compute="_compute_fund_amounts",
        store=True,
        readonly=False,
        help="ยอดเงินที่จ่ายเข้ากองทุนประกันสังคมทั้งปีภาษี "
             "ดึงจากหน้าทำเงินเดือนให้เป็นค่าเริ่มต้น — แก้ไขเองได้",
    )
    provident_fund_amount = fields.Float(
        string="กองทุนสำรองเลี้ยงชีพ (ทั้งปี)",
        compute="_compute_fund_amounts",
        store=True,
        readonly=False,
        help="ยอดเงินที่จ่ายเข้ากองทุนสำรองเลี้ยงชีพทั้งปีภาษี "
             "ดึงจากหน้าทำเงินเดือนให้เป็นค่าเริ่มต้น — แก้ไขเองได้",
    )
    employee_id = fields.Many2one(
        comodel_name="employee.salary",
        string="ชื่อพนักงาน",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        ondelete="restrict",
        tracking=True,
    )
    employee_firstname = fields.Char(
        string="ชื่อ",
        related="employee_id.firstname",
        store=True,
        readonly=True,
    )
    employee_lastname = fields.Char(
        string="นามสกุล",
        related="employee_id.lastname",
        store=True,
        readonly=True,
    )
    employee_taxid = fields.Char(
        string="เลขประจำตัวผู้เสียภาษี (พนักงาน)",
        related="employee_id.id_card_number",
        readonly=True,
    )
    employee_address = fields.Char(
        string="ที่อยู่ (พนักงาน)",
        related="employee_id.address",
        store=True,
        readonly=True,
    )
    employee_resign_date = fields.Date(
        string="วันที่ออกจากงาน",
        related="employee_id.resign_date",
        store=True,
        readonly=True,
        help="ดึงจากหน้าข้อมูลพนักงาน — ถ้าลาออกในปีภาษีนี้ ระบบจะนับยอด "
             "ประกันสังคม/กองทุนสำรองเลี้ยงชีพ ถึงเดือนที่ลาออกเท่านั้น",
    )
    pnd1_full_name = fields.Char(
        string="ชื่อ-นามสกุล (จากรายงาน ภ.ง.ด.1)",
        compute="_compute_pnd1_full_name",
        help="ดึงชื่อจากรายงาน ภ.ง.ด.1 (pnd1.line) โดยจับคู่จากเลขบัตรประชาชน "
             "ถ้าไม่พบใช้ชื่อจากข้อมูลพนักงานแทน",
    )
    company_name = fields.Char(
        string="บริษัท",
        compute="_compute_company_name",
        store=True,
        readonly=True,
    )
    company_address = fields.Char(
        string="ที่อยู่บริษัท",
        default="85/13-16 ถนนบรมราชชนนี, แขวงอรุณอมรินทร์, เขตบางกอกน้อย, จ.กรุงเทพมหานคร, 10700, ประเทศไทย",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    company_taxid = fields.Char(
        string="เลขประจำตัวผู้เสียภาษี (บริษัท)",
        default="0105560151261",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    branch_id = fields.Many2one(
        comodel_name="hr.branch.custom",
        string="สาขา",
        compute="_compute_branch",
        store=True,
        readonly=True,
    )
    income_tax_form = fields.Selection(
        selection=INCOME_TAX_FORM,
        string="Income Tax Form",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        default="pnd1",
        copy=False,
        help="PND1 (ภ.ง.ด.1) สำหรับหักภาษี ณ ที่จ่ายจากเงินเดือน 40(1)",
    )
    tax_payer = fields.Selection(
        selection=TAX_PAYER,
        string="Tax Payer",
        default="withholding",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        copy=False,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    wt_line = fields.One2many(
        comodel_name="hr.withholding.tax.cert.line",
        inverse_name="cert_id",
        string="Withholding Tax Lines",
        readonly=True,
        states={"draft": [("readonly", False)]},
        copy=False,
    )

    @api.depends("employee_id", "employee_id.company")
    def _compute_company_name(self):
        for rec in self:
            rec.company_name = rec.employee_id.company or ""

    @api.depends("employee_id")
    def _compute_branch(self):
        branch = self.env["hr.branch.custom"].search(
            [("name", "=", "สำนักงานใหญ่")], limit=1
        )
        for rec in self:
            rec.branch_id = branch.id if branch else False

    @api.depends("employee_id", "employee_id.id_card_number",
                 "employee_firstname", "employee_lastname")
    def _compute_pnd1_full_name(self):
        """ใช้ชื่อจากรายงาน ภ.ง.ด.1 (pnd1.line) แทนชื่อจากหน้าทำเงินเดือน
        จับคู่จากเลขบัตรประชาชนของพนักงาน — ถ้าไม่พบ fallback เป็นชื่อ+นามสกุลเดิม"""
        Pnd1 = self.env["pnd1.line"]
        for rec in self:
            name = ""
            taxid = rec.employee_id.id_card_number or ""
            if taxid:
                line = Pnd1.search(
                    [("id_card_number", "=", taxid), ("full_name", "!=", False)],
                    order="pay_date desc, id desc", limit=1,
                )
                name = (line.full_name or "").strip()
            if not name:
                name = ("%s %s" % (
                    rec.employee_firstname or "",
                    rec.employee_lastname or "")).strip()
            rec.pnd1_full_name = name

    @api.model
    def _pnd1_gregorian_year(self, report_year):
        """แปลงปีที่กรอก (ค.ศ. หรือ พ.ศ.) เป็นปี ค.ศ. (int) — คืน 0 ถ้าแปลงไม่ได้"""
        try:
            y = int(report_year)
        except (TypeError, ValueError):
            return 0
        return y - 543 if y >= 2500 else y

    @api.model
    def _get_pnd1_totals(self, taxid, company, report_year):
        """รวม 'จำนวนเงินได้' + 'ภาษีที่ต้องหัก' จากรายงาน ภ.ง.ด.1 (pnd1.line)
        ของเลขบัตรนี้ในปีที่ระบุ — จับคู่จากเลขบัตร (+ บริษัท ถ้ามี),
        กรองปีจากวันที่จ่าย (pay_date). คืนค่า (เงินได้รวม, ภาษีรวม)"""
        taxid = taxid or ""
        if not taxid:
            return 0.0, 0.0
        domain = [("id_card_number", "=", taxid)]
        if company:
            domain.append(("company", "=", company))
        y = self._pnd1_gregorian_year(report_year)
        if y:
            # นับทั้งปี ค.ศ. (y) และ พ.ศ. (y+543) ของปีภาษีเดียวกัน
            # เพราะบางแถว (เช่น นำเข้าจาก excel) วันที่ถูกเก็บเป็น พ.ศ.
            yb = y + 543
            domain += [
                "|",
                "&", ("pay_date", ">=", "%04d-01-01" % y), ("pay_date", "<=", "%04d-12-31" % y),
                "&", ("pay_date", ">=", "%04d-01-01" % yb), ("pay_date", "<=", "%04d-12-31" % yb),
            ]
        lines = self.env["pnd1.line"].search(domain)
        return sum(lines.mapped("income")), sum(lines.mapped("tax"))

    @api.depends("employee_id", "employee_id.id_card_number", "employee_id.company",
                 "report_year")
    def _compute_total_net_salary(self):
        for rec in self:
            income, tax = rec._get_pnd1_totals(
                rec.employee_id.id_card_number, rec.employee_id.company, rec.report_year)
            # fallback: ถ้ายังไม่มีข้อมูลใน ภ.ง.ด.1 → ใช้เงินสุทธิจากระบบเงินเดือน × 3%
            # (ให้ตรงกับยอดที่ wizard/onchange ใช้สร้าง wt_line เมื่อไม่มีข้อมูล ภ.ง.ด.1)
            if not income and not tax and rec.employee_id and rec.report_year:
                payrolls = self.env["payroll.salary"].search([
                    ("employee_id", "=", rec.employee_id.id),
                    ("year", "=", rec.report_year),
                ])
                income = sum(payrolls.mapped("net_salary"))
                tax = income * 3.0 / 100
            rec.total_net_salary = income
            rec.total_tax = tax

    # ------------------------------------------------------------------
    # ประกันสังคม / กองทุนสำรองเลี้ยงชีพ — ดึงจากหน้าทำเงินเดือน (payroll.salary)
    # ------------------------------------------------------------------
    PROVIDENT_LINE_NAME = "กองทุนสำรองเลี้ยงชีพ"

    @api.model
    def _get_payroll_last_month(self, employee, gregorian_year):
        """เดือนสุดท้ายของปีภาษีที่นับยอดให้พนักงานคนนี้ (1-12)

        ยึด "วันที่ออกจากงาน" (resign_date) ในหน้าข้อมูลพนักงาน — พนักงานแต่ละคน
        ออกคนละเดือน จึงต้องตัดเป็นรายคน:
          - ลาออกในปีภาษีนี้ → นับถึงเดือนที่ลาออก (เดือนล่าสุดที่คนนั้นออก)
          - ลาออกไปก่อนปีภาษีนี้ → ไม่มียอดของปีนี้ (คืน 0)
          - ยังไม่ลาออก / ลาออกหลังปีนี้ → นับครบ 12 เดือน
        """
        resign_date = getattr(employee, "resign_date", False)
        if not resign_date:
            return 12
        if resign_date.year < gregorian_year:
            return 0
        if resign_date.year == gregorian_year:
            return resign_date.month
        return 12

    @api.model
    def _get_fund_totals(self, employee, report_year):
        """รวมยอด "ประกันสังคม" + "กองทุนสำรองเลี้ยงชีพ" ทั้งปีภาษีจากหน้าทำเงินเดือน

        - จับคู่รอบเงินเดือนจากปีที่ระบุ (รองรับทั้ง ค.ศ. และ พ.ศ. ที่เก็บในฟิลด์ year)
        - ตัดตามวันที่ออกจากงานของพนักงานแต่ละคน (ดู _get_payroll_last_month)
        - ประกันสังคม: ใช้ "ประกันสังคมสะสม" ของรอบเดือนล่าสุด = ยอดที่หักจริงทั้งปีภาษี
          (รวมยอดต้นรอบที่ยกมาจากระบบเก่าด้วย) — ถ้าไม่มี fallback เป็นผลรวมรายเดือน
        - กองทุนสำรองเลี้ยงชีพ: ไม่มียอดสะสม → รวมรายเดือนจากบรรทัดหักในสลิป
          (ครอบคลุมทั้งแบบกรอกยอดเองและแบบคิดตามอัตรา %)
        คืนค่า (ประกันสังคมทั้งปี, กองทุนสำรองเลี้ยงชีพทั้งปี)
        """
        if not employee or not report_year:
            return 0.0, 0.0
        year = self._pnd1_gregorian_year(report_year)
        if not year:
            return 0.0, 0.0

        last_month = self._get_payroll_last_month(employee, year)
        if not last_month:
            return 0.0, 0.0

        payrolls = self.env["payroll.salary"].search(
            [
                ("employee_id", "=", employee.id),
                ("year", "in", [str(year), str(year + 543)]),
                ("month", "<=", last_month),
            ],
            order="month asc",
        )
        if not payrolls:
            return 0.0, 0.0

        sso = payrolls[-1].accumulated_social_security or 0.0
        if not sso:
            sso = sum(payrolls.mapped("sso_total"))

        provident = 0.0
        for payroll in payrolls:
            month_pf = sum(
                payroll.line_ids.filtered(
                    lambda l: l.type == "deduction"
                    and (l.name or "").strip() == self.PROVIDENT_LINE_NAME
                ).mapped("amount")
            )
            provident += month_pf or (payroll.expense_provident or 0.0)

        return sso, provident

    @api.depends("employee_id", "employee_id.resign_date", "report_year")
    def _compute_fund_amounts(self):
        for rec in self:
            sso, provident = rec._get_fund_totals(rec.employee_id, rec.report_year)
            rec.sso_amount = sso
            rec.provident_fund_amount = provident

    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("hr.withholding.tax.cert")
                or _("New")
            )
        return super().create(vals)

    @api.onchange("employee_id", "report_year")
    def _onchange_employee_year(self):
        """เลือกพนักงาน/เปลี่ยนปี → ดึงเงินได้+ภาษีจากรายงาน ภ.ง.ด.1 → สร้าง line อัตโนมัติ"""
        if self.employee_id and self.report_year:
            income, tax = self._get_pnd1_totals(
                self.employee_id.id_card_number, self.employee_id.company, self.report_year)
            # fallback: ถ้ายังไม่มีข้อมูลใน ภ.ง.ด.1 → net_salary × 3% (เหมือนเดิม)
            if not income and not tax:
                payrolls = self.env["payroll.salary"].search([
                    ("employee_id", "=", self.employee_id.id),
                    ("year", "=", self.report_year),
                ])
                income = sum(payrolls.mapped("net_salary"))
                tax = income * 3.0 / 100
            self.wt_line = [(5, 0, 0)]
            if income:
                wt_percent = (tax / income * 100) if income else 0.0
                self.wt_line = [
                    (
                        0,
                        0,
                        {
                            "wt_cert_income_type": "1",
                            "wt_cert_income_desc": "เงินเดือน ค่าจ้าง เบี้ยเลี้ยง โบนัส ฯลฯ 40(1)",
                            "base": income,
                            "wt_percent": wt_percent,
                            "amount": tax,
                        },
                    )
                ]

    def action_draft(self):
        self.write({"state": "draft"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancel"})


class HRWithholdingTaxCertLine(models.Model):
    _name = "hr.withholding.tax.cert.line"
    _description = "HR Withholding Tax Cert Lines"

    cert_id = fields.Many2one(
        comodel_name="hr.withholding.tax.cert",
        index=True,
        ondelete="cascade",
    )
    wt_cert_income_type = fields.Selection(
        selection=WHT_CERT_INCOME_TYPE,
        string="Type of Income",
        required=True,
    )
    wt_cert_income_desc = fields.Char(
        string="Income Description",
        size=500,
    )
    base = fields.Float(string="Base Amount")
    wt_percent = fields.Float(string="% Tax")
    amount = fields.Float(string="Tax Amount")

    @api.onchange("wt_cert_income_type")
    def _onchange_wt_cert_income_type(self):
        if self.wt_cert_income_type:
            select_dict = dict(WHT_CERT_INCOME_TYPE)
            self.wt_cert_income_desc = select_dict.get(
                self.wt_cert_income_type, ""
            )

    @api.onchange("wt_percent", "base")
    def _onchange_wt_percent(self):
        if self.wt_percent and self.base:
            self.amount = self.base * self.wt_percent / 100

    @api.constrains("base", "wt_percent", "amount")
    def _check_wt_line(self):
        for rec in self:
            if rec.wt_percent and rec.base:
                expected = rec.base * rec.wt_percent / 100
                if abs(rec.amount - expected) > 0.01:
                    raise ValidationError(
                        _(
                            "Tax Amount (%.2f) does not match "
                            "Base Amount (%.2f) x %% Tax (%.2f) = %.2f"
                        )
                        % (rec.amount, rec.base, rec.wt_percent, expected)
                    )
