# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import date, timedelta


class ResCompany(models.Model):
    _inherit = "res.company"

    sh_notify_day = fields.Integer(string="Days Before Expired Medical")
    sh_partner_ids = fields.Many2many("res.partner", string="Notify Users")
    sh_expired_medical_type_ids = fields.One2many(
        "sh.expired.hr.employee.line", "company_id", string="Medical Type")

    @api.model
    def _run_notify_email_from_employee(self):
        company_id = self.env["res.company"].sudo().search(
            [("id", "=", 1)], limit=1)
        if company_id:
            company_id.sh_expired_medical_type_ids.unlink()
            notify_list = []
            for line in self.env["sh.hr.employee.line"].sudo().search([]):
                date_obj = line.sh_expiry_date
                date_before = (
                    date_obj-timedelta(days=company_id.sh_notify_day))
                if date.today() == date_before:
                    notify_vals = {
                        "company_id": company_id.id,
                        "employee_id": line.employee_id.id,
                        "sh_medical_type_id": line.sh_medical_type_id.id,
                        "sh_issue_date": line.sh_issue_date,
                        "sh_expiry_month": line.sh_expiry_month,
                        "sh_expiry_date": line.sh_expiry_date,
                        "sh_description": line.sh_description,
                    }
                    notify_list.append((0, 0, notify_vals))
            if notify_list:
                company_id.sh_expired_medical_type_ids = notify_list
                template = self.env.ref(
                    "sh_all_in_one_hrms.sh_expired_medical_email_template",
                    raise_if_not_found=False)
                if template:
                    field = ["subject", "body_html", "email_from", "email_to", "partner_to",
                             "email_cc",  "reply_to", "attachment_ids", "mail_server_id"]
                    values = self.env["mail.template"].browse(
                        template.id).generate_email(company_id.id, fields=field)
                    values.update({
                        "recipient_ids": [(6, 0, company_id.sh_partner_ids.ids)],
                    })
                    template.send_mail(company_id.id,
                                       force_send=False,
                                       email_values=values)


class ShExpiredEmployeeLine(models.Model):
    _name = "sh.expired.hr.employee.line"
    _description = "Expired Medical Examination"
    _rec_name = "employee_id"
    _order = "id desc"

    company_id = fields.Many2one("res.company", string="Company")
    employee_id = fields.Many2one("hr.employee", string="Employee")
    sh_medical_type_id = fields.Many2one(
        "sh.medical.type", string="Medical Type")
    sh_issue_date = fields.Date("Issued Date")
    sh_expiry_month = fields.Integer("Expire time in (Month)")
    sh_expiry_date = fields.Date("Expiry Date")
    sh_description = fields.Char("Description")


class EmployeeConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sh_notify_day = fields.Integer(
        string="Days Before Expired Medical",
        related="company_id.sh_notify_day",
        readonly=False)
    sh_partner_ids = fields.Many2many(
        "res.partner", string="Notify Users",
        related="company_id.sh_partner_ids",
        readonly=False)
    group_hide_menu_emp_medical = fields.Boolean(
        "Enable Employee Medical Examination", implied_group='sh_all_in_one_hrms.group_hide_menu_emp_medical')


class ShEmployee(models.Model):
    _inherit = "hr.employee"

    sh_medical_type_ids = fields.One2many(
        "sh.hr.employee.line", "employee_id", string="Medical Examination")
    sh_doctor_id = fields.Many2one("res.partner", string="Doctor")
    sh_phone = fields.Char(string="Phone")
    sh_blood_group = fields.Char(string="Blood Group")
    sh_height = fields.Float(string="Height")
    sh_weight = fields.Float(string="Weight")
    sh_eyes = fields.Boolean(string="Eyes")
    sh_respiratory = fields.Boolean(string="Respiratory")
    sh_musculoskeletal = fields.Boolean(string="Musculoskeletal")
    sh_ears = fields.Boolean(string="Ears")
    sh_cardiovascular = fields.Boolean(string="Cardiovascular")
    sh_dermatological = fields.Boolean(string="Dermatological")
    sh_nose_throat = fields.Boolean(string="Nose & Throat")
    sh_neurological = fields.Boolean(string="Neurological")
    sh_blood_pressure = fields.Boolean(string="Blood Pressure")
    sh_notes = fields.Text(string="Medical Notes")


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    sh_doctor_id = fields.Many2one("res.partner", string="Doctor")
    sh_phone = fields.Char(string="Phone")
    sh_blood_group = fields.Char(string="Blood Group")
    sh_height = fields.Float(string="Height")
    sh_weight = fields.Float(string="Weight")
    sh_eyes = fields.Boolean(string="Eyes")
    sh_respiratory = fields.Boolean(string="Respiratory")
    sh_musculoskeletal = fields.Boolean(string="Musculoskeletal")
    sh_ears = fields.Boolean(string="Ears")
    sh_cardiovascular = fields.Boolean(string="Cardiovascular")
    sh_dermatological = fields.Boolean(string="Dermatological")
    sh_nose_throat = fields.Boolean(string="Nose & Throat")
    sh_neurological = fields.Boolean(string="Neurological")
    sh_blood_pressure = fields.Boolean(string="Blood Pressure")
    sh_notes = fields.Text(string="Medical Notes")


class ShEmployeeLine(models.Model):
    _name = "sh.hr.employee.line"
    _description = "Employee Line"
    _rec_name = "employee_id"
    _order = "id desc"

    employee_id = fields.Many2one("hr.employee", string="Employee")
    sh_medical_type_id = fields.Many2one(
        "sh.medical.type", string="Medical Type", required=True)
    sh_issue_date = fields.Date("Issued Date", required=True)
    sh_expiry_month = fields.Integer("Expire time in (Month)", required=True)
    sh_expiry_date = fields.Date(
        "Expiry Date", compute="_compute_expiry_date", store=True)
    sh_description = fields.Char("Description", required=True)
    company_id = fields.Many2one("res.company",
                                 string="Company",
                                 default=lambda self: self.env.company)

    @api.depends("sh_issue_date", "sh_expiry_month")
    def _compute_expiry_date(self):
        if self:
            for rec in self:
                if rec.sh_issue_date != False:
                    date_obj = rec.sh_issue_date
                    expiry_date = date_obj + \
                        relativedelta(months=rec.sh_expiry_month)
                    rec.sh_expiry_date = expiry_date
