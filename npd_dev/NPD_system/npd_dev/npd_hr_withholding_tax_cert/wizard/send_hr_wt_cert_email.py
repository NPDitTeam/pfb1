import base64
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SendHRWTCertEmail(models.TransientModel):
    _name = "send.hr.wt.cert.email"
    _description = "Send HR WT Certificate Email"

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587
    SMTP_USER = "npdsgroup.official@gmail.com"
    SMTP_PASS = "unyd dkpb pclr iodq"
    SMTP_ENCRYPTION = "starttls"

    year = fields.Char(
        string="ปี (ค.ศ.)",
        required=True,
        default=lambda self: str(fields.Date.today().year),
    )
    send_to = fields.Selection(
        [("all", "ทั้งหมด"), ("selected", "เลือกพนักงาน")],
        string="ส่งถึง",
        default="all",
        required=True,
    )
    employee_ids = fields.Many2many(
        comodel_name="employee.salary",
        string="พนักงาน",
        relation="send_wt_cert_email_employee_rel",
    )
    cert_count = fields.Integer(
        string="จำนวน WT Cert ที่พบ",
        compute="_compute_cert_count",
    )
    no_email_warning = fields.Text(
        string="พนักงานที่ไม่มีอีเมล",
        compute="_compute_cert_count",
    )

    @api.depends("year", "send_to", "employee_ids")
    def _compute_cert_count(self):
        Cert = self.env["hr.withholding.tax.cert"]
        for rec in self:
            domain = [
                ("report_year", "=", rec.year),
                ("state", "=", "done"),
            ]
            if rec.send_to == "selected" and rec.employee_ids:
                domain.append(("employee_id", "in", rec.employee_ids.ids))
            certs = Cert.search(domain)
            rec.cert_count = len(certs)
            # Check employees without email
            no_email = []
            for cert in certs:
                emp = cert.employee_id
                if not emp.email:
                    no_email.append(
                        "%s %s" % (emp.firstname or "", emp.lastname or "")
                    )
            if no_email:
                rec.no_email_warning = (
                    "พนักงานต่อไปนี้ไม่มีอีเมล (จะไม่ได้รับเมล):\n"
                    + "\n".join("- %s" % name for name in no_email)
                )
            else:
                rec.no_email_warning = False

    @api.onchange("year")
    def _onchange_year(self):
        """Filter employee_ids domain to only employees with certs in this year"""
        if self.year:
            certs = self.env["hr.withholding.tax.cert"].search([
                ("report_year", "=", self.year),
                ("state", "=", "done"),
            ])
            return {
                "domain": {
                    "employee_ids": [("id", "in", certs.mapped("employee_id").ids)]
                }
            }

    def action_send_email(self):
        self.ensure_one()
        Cert = self.env["hr.withholding.tax.cert"]

        domain = [
            ("report_year", "=", self.year),
            ("state", "=", "done"),
        ]
        if self.send_to == "selected" and self.employee_ids:
            domain.append(("employee_id", "in", self.employee_ids.ids))

        certs = Cert.search(domain)
        if not certs:
            raise UserError(_("ไม่พบ WT Certificate (สถานะ Done) ในปี %s") % self.year)

        # Get the report action for PDF generation
        report = self.env.ref("npd_hr_wt_cert_form.hr_wt_cert_pdf_report", False)
        if not report:
            raise UserError(
                _("ไม่พบรายงาน HR WT Certificates (pdf) กรุณาติดตั้งโมดูล npd_hr_wt_cert_form")
            )

        success_count = 0
        fail_count = 0
        no_email_employees = []

        for cert in certs:
            employee = cert.employee_id
            email_to = employee.email
            if not email_to:
                no_email_employees.append(
                    "%s %s" % (employee.firstname or "", employee.lastname or "")
                )
                fail_count += 1
                continue

            # Generate PDF
            try:
                pdf_content, content_type = report._render_qweb_pdf([cert.id])
            except Exception as e:
                _logger.error("Failed to generate PDF for cert %s: %s", cert.name, e)
                fail_count += 1
                continue

            # Create attachment
            attachment = self.env["ir.attachment"].create({
                "name": "WT_Certificate_%s_%s.pdf" % (
                    cert.name,
                    (employee.firstname or "") + "_" + (employee.lastname or ""),
                ),
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "res_model": "hr.withholding.tax.cert",
                "res_id": cert.id,
                "mimetype": "application/pdf",
            })

            # Compose email
            employee_name = "%s %s" % (
                employee.firstname or "",
                employee.lastname or "",
            )
            subject = "หนังสือรับรองหัก ณ ที่จ่าย ประจำปี %s - %s" % (
                self.year,
                employee_name,
            )

            # Build summary from wt_line
            line_details = []
            for line in cert.wt_line:
                line_details.append(
                    "  - %s : ฐาน %s บาท, ภาษี %s บาท (%.2f%%)" % (
                        line.wt_cert_income_desc or "",
                        "{:,.2f}".format(line.base),
                        "{:,.2f}".format(line.amount),
                        line.wt_percent,
                    )
                )
            total_base = sum(cert.wt_line.mapped("base"))
            total_tax = sum(cert.wt_line.mapped("amount"))

            body = (
                "เรียน คุณ%s\n\n"
                "ฝ่ายบุคคลส่วนกลาง ขอส่งหนังสือรับรองหัก ณ ที่จ่าย มาเพื่อทราบ\n\n"
                "สรุป WT Certificate\n"
                "  เลขที่: %s\n"
                "  ประจำปี: %s\n"
                "  บริษัท: %s\n"
                "  เงินสุทธิรวมทั้งปี: %s บาท\n\n"
                "รายการหัก ณ ที่จ่าย:\n%s\n\n"
                "  รวมฐานภาษี: %s บาท\n"
                "  รวมภาษีหัก ณ ที่จ่าย: %s บาท\n\n"
                "กรุณาตรวจสอบความถูกต้อง หากมีข้อสงสัยกรุณาติดต่อฝ่ายบุคคล\n\n"
                "ขอแสดงความนับถือ\n"
                "ฝ่ายบุคคลส่วนกลาง (HR)"
            ) % (
                employee_name,
                cert.name or "",
                self.year,
                cert.company_name or "",
                "{:,.2f}".format(cert.total_net_salary),
                "\n".join(line_details) if line_details else "  - ไม่มีรายการ",
                "{:,.2f}".format(total_base),
                "{:,.2f}".format(total_tax),
            )

            try:
                self._send_email_smtp(
                    email_from=self.SMTP_USER,
                    email_to=email_to,
                    subject=subject,
                    body=body,
                    attachments=[attachment],
                )
                # Log to chatter
                cert.message_post(
                    body=_("ส่งเมล WT Certificate ไปที่ %s สำเร็จ") % email_to,
                    message_type="notification",
                )
                success_count += 1
            except Exception as e:
                _logger.error(
                    "Failed to send email for cert %s to %s: %s",
                    cert.name, email_to, e,
                )
                fail_count += 1

        # Build result message
        msg_parts = []
        msg_parts.append("ส่งเมลสำเร็จ: %d ฉบับ" % success_count)
        if fail_count:
            msg_parts.append("ส่งไม่สำเร็จ: %d ฉบับ" % fail_count)
        if no_email_employees:
            msg_parts.append(
                "พนักงานที่ไม่มีอีเมล: %s" % ", ".join(no_email_employees)
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ผลการส่งเมล WT Certificate"),
                "message": "\n".join(msg_parts),
                "type": "success" if not fail_count else "warning",
                "sticky": True,
            },
        }

    def _send_email_smtp(self, email_from, email_to, subject, body, attachments=None):
        msg = MIMEMultipart()
        msg["From"] = email_from
        msg["To"] = email_to
        msg["Subject"] = subject

        body_html = (
            '<html><body>'
            '<pre style="font-family: Tahoma, sans-serif; font-size: 14px;">'
            '%s</pre></body></html>'
        ) % body.replace("\n", "<br/>")
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        if attachments:
            for attachment in attachments:
                part = MIMEBase("application", "octet-stream")
                file_data = (
                    base64.b64decode(attachment.datas) if attachment.datas else b""
                )
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment.name or "attachment",
                )
                msg.attach(part)

        try:
            if self.SMTP_ENCRYPTION == "ssl":
                server = smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT, timeout=30)
            else:
                server = smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT, timeout=30)
                if self.SMTP_ENCRYPTION == "starttls":
                    server.starttls()

            server.login(self.SMTP_USER, self.SMTP_PASS)
            server.sendmail(email_from, [email_to], msg.as_string())
            server.quit()
        except smtplib.SMTPAuthenticationError:
            raise UserError(
                _("การยืนยันตัวตน SMTP ล้มเหลว กรุณาตรวจสอบ username/password")
            )
        except smtplib.SMTPConnectError:
            raise UserError(
                _("ไม่สามารถเชื่อมต่อ SMTP server ได้ กรุณาตรวจสอบ host/port")
            )
        except Exception as e:
            raise UserError(_("ส่งเมลไม่สำเร็จ: %s") % str(e))
