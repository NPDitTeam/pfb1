import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GenerateHRWTCert(models.TransientModel):
    _name = "generate.hr.wt.cert"
    _description = "Generate HR WT Certificates for All Employees"

    year = fields.Char(
        string="ปี (ค.ศ.)",
        required=True,
        default=lambda self: str(fields.Date.today().year),
        help="ค้นหาพนักงานที่มีข้อมูลเงินเดือนในปีนี้",
    )

    def _get_employees_in_year(self, payrolls, pnd1_lines):
        """พนักงานที่มีข้อมูลในปีนี้: มีรอบเงินเดือน / มีแถว ภ.ง.ด.1 จากระบบ /
        เลขบัตรตรงกับแถวที่นำเข้าจาก excel (รวมคนที่ออกก่อนระบบเริ่มดึงเงินเดือน)"""
        Cert = self.env["hr.withholding.tax.cert"]
        employees = payrolls.mapped("employee_id") | pnd1_lines.mapped("employee_id")
        excel_taxids = {
            Cert._normalize_taxid(t)
            for t in pnd1_lines.filtered(lambda l: not l.employee_id).mapped("id_card_number")
        }
        excel_taxids.discard("")
        if excel_taxids:
            for emp in self.env["employee.salary"].search([("id_card_number", "!=", False)]):
                if Cert._normalize_taxid(emp.id_card_number) in excel_taxids:
                    employees |= emp
        return employees

    def action_generate_all(self):
        self.ensure_one()
        Cert = self.env["hr.withholding.tax.cert"]
        Payroll = self.env["payroll.salary"]

        payrolls = Payroll.search([("year", "=", self.year)])
        pnd1_lines = self.env["pnd1.line"].search(Cert._pnd1_year_domain(self.year))
        employees = self._get_employees_in_year(payrolls, pnd1_lines)
        if not employees:
            raise UserError(
                _("ไม่พบข้อมูลเงินเดือนหรือรายงาน ภ.ง.ด.1 ในปี %s") % self.year
            )

        created_count = 0
        updated_count = 0

        for employee in employees:
            # ออกหนังสือรับรองแยกตามบริษัทผู้จ่าย — ย้ายบริษัทกลางปีได้ใบของแต่ละบริษัท
            companies = set(Cert._get_pnd1_lines(employee, self.year).mapped("company"))
            if not companies and employee.company:
                companies = {employee.company}

            for company in sorted(companies):
                # ดึงเงินได้ + ภาษี จากรายงาน ภ.ง.ด.1 ของบริษัทนี้ในปีนี้
                income_total, tax_total = Cert._get_pnd1_totals(employee, company, self.year)
                # fallback: ถ้ายังไม่มีข้อมูลใน ภ.ง.ด.1 → รายรับ (รวมรายได้) × 3%
                if not income_total and not tax_total:
                    emp_payrolls = payrolls.filtered(
                        lambda p: p.employee_id == employee
                    )
                    income_total = sum(emp_payrolls.mapped("total_gross"))
                    tax_total = income_total * 3.0 / 100
                if not income_total:
                    continue

                wt_percent = (tax_total / income_total * 100) if income_total else 0.0

                # ประกันสังคม + กองทุนสำรองเลี้ยงชีพ ทั้งปีของบริษัทนี้
                # (ตัดตามวันที่ออกจากงานของแต่ละคน)
                sso_amount, provident_amount = Cert._get_fund_totals(
                    employee, self.year, company)

                line_vals = {
                    "wt_cert_income_type": "1",
                    "wt_cert_income_desc": "เงินเดือน ค่าจ้าง เบี้ยเลี้ยง โบนัส ฯลฯ 40(1)",
                    "base": income_total,
                    "wt_percent": wt_percent,
                    "amount": tax_total,
                }

                existing = Cert.search([
                    ("employee_id", "=", employee.id),
                    ("report_year", "=", self.year),
                    ("company_name", "=", company),
                ], limit=1)

                if existing:
                    # Update: reset to draft, clear lines, re-create, then done
                    if existing.state != "draft":
                        existing.write({"state": "draft"})
                    existing.wt_line.unlink()
                    existing.write({
                        "wt_line": [(0, 0, line_vals)],
                        "sso_amount": sso_amount,
                        "provident_fund_amount": provident_amount,
                        "state": "done",
                    })
                    updated_count += 1
                else:
                    # Create new cert and set to done
                    cert = Cert.create({
                        "employee_id": employee.id,
                        "report_year": self.year,
                        "company_name": company,
                        "income_tax_form": "pnd1",
                        "tax_payer": "withholding",
                        "sso_amount": sso_amount,
                        "provident_fund_amount": provident_amount,
                        "wt_line": [(0, 0, line_vals)],
                    })
                    cert.write({"state": "done"})
                    created_count += 1

        _logger.info("[WT CERT] ปี %s สร้าง %d ใบ อัพเดท %d ใบ",
                     self.year, created_count, updated_count)

        # Return action to show all certs for this year (list view)
        action = self.env.ref(
            "npd_hr_withholding_tax_cert.action_hr_withholding_tax_cert"
        ).read()[0]
        action["domain"] = [("report_year", "=", self.year)]
        action["context"] = {"default_report_year": self.year}
        return action
