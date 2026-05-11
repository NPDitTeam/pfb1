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

    def action_generate_all(self):
        self.ensure_one()
        Cert = self.env["hr.withholding.tax.cert"]
        Payroll = self.env["payroll.salary"]

        # Find all unique employees who have payroll records for this year
        payrolls = Payroll.search([("year", "=", self.year)])
        if not payrolls:
            raise UserError(
                _("ไม่พบข้อมูลเงินเดือนในปี %s") % self.year
            )

        employee_ids = payrolls.mapped("employee_id")
        created_count = 0
        updated_count = 0

        for employee in employee_ids:
            # Sum net_salary for all months of this employee in this year
            emp_payrolls = payrolls.filtered(
                lambda p: p.employee_id == employee
            )
            total_net = sum(emp_payrolls.mapped("net_salary"))
            if not total_net:
                continue

            wt_percent = 3.0
            amount = total_net * wt_percent / 100

            line_vals = {
                "wt_cert_income_type": "1",
                "wt_cert_income_desc": "เงินเดือน ค่าจ้าง เบี้ยเลี้ยง โบนัส ฯลฯ 40(1)",
                "base": total_net,
                "wt_percent": wt_percent,
                "amount": amount,
            }

            # Check if cert already exists for this employee + year
            existing = Cert.search([
                ("employee_id", "=", employee.id),
                ("report_year", "=", self.year),
            ], limit=1)

            if existing:
                # Update: reset to draft, clear lines, re-create, then done
                if existing.state != "draft":
                    existing.write({"state": "draft"})
                existing.wt_line.unlink()
                existing.write({
                    "wt_line": [(0, 0, line_vals)],
                    "state": "done",
                })
                updated_count += 1
            else:
                # Create new cert and set to done
                cert = Cert.create({
                    "employee_id": employee.id,
                    "report_year": self.year,
                    "income_tax_form": "pnd1",
                    "tax_payer": "withholding",
                    "wt_line": [(0, 0, line_vals)],
                })
                cert.write({"state": "done"})
                created_count += 1

        # Return action to show all certs for this year (list view)
        action = self.env.ref(
            "npd_hr_withholding_tax_cert.action_hr_withholding_tax_cert"
        ).read()[0]
        action["domain"] = [("report_year", "=", self.year)]
        action["context"] = {"default_report_year": self.year}
        return action
