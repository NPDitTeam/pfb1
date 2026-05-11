# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import api, fields, models
from datetime import datetime
from dateutil.relativedelta import relativedelta

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_emp_extra_field = fields.Boolean(
        "Enable Employee Extra Fields", implied_group='sh_all_in_one_hrms.group_enable_emp_extra_field')


# Employee Inherit


class ShEmployeeExtraFields(models.Model):
    _inherit = 'hr.employee'

    work_country_id = fields.Many2one('res.country', string='Work Country')
    reference_by_id = fields.Many2one('hr.employee', string='Reference By')
    previous_nationality_id = fields.Many2one(
        'res.country', string='Previous Nationality')
    passport_country_id = fields.Many2one(
        'res.country', string='Passport Country')
    passport_issue = fields.Date(string='Passport Issue Date', default=lambda self: self._context.get(
        'date', fields.Date.context_today(self)))
    passport_expiry = fields.Date(string='Passport Expiry Date', default=lambda self: self._context.get(
        'date', fields.Date.context_today(self)))
    religion_id = fields.Many2one('sh.employee.religion', string='Religion')
    height = fields.Float("Height")
    weight = fields.Float("Weight")
    blood_group = fields.Selection([('A +ve', 'A +ve'), ('A -ve', 'A -ve'),
                                    ('B +ve', 'B +ve'), ('B -ve', 'B -ve'),
                                    ('AB +ve', 'AB +ve'), ('AB -ve', 'AB -ve'),
                                    ('O +ve', 'O +ve'), ('O -ve', 'O -ve'), ],
                                   string='Blood Group', copy=False)
    age = fields.Integer('Age', compute="_compute_age")
    joining_date = fields.Date(string="Joining Date")
    employment_date = fields.Date(string="Employment Date")
    confirmation_date = fields.Date(string="Confirmation Date")
    marriage_date = fields.Date(string="Marriage Date")
    is_part_time = fields.Boolean("Is Part Time")
    pf_acc_no = fields.Char('PF Account No.')
    facilities_cmp_ids = fields.Many2many(
        'sh.company.facilities', string="Facilities By Company")
    skype = fields.Char('Skype')
    whatsapp = fields.Char('Whatsapp')
    facebook = fields.Char('Facebook')
    instagram = fields.Char('Instagram')
    twitter = fields.Char('Twitter')
    personal_email = fields.Char('Personal Email')

    certification_ids = fields.One2many('sh.certification', 'cert_employee_id')
    emergency_ids = fields.One2many(
        'hr.emp.emmergancy', 'employee_id', string='Employee Emergency Contact')

    @api.onchange('birthday')
    def _compute_age(self):
        self.age = False
        if self.birthday:
            d1 = self.birthday
            d2 = datetime.today()
            self.age = relativedelta(d2, d1).years
