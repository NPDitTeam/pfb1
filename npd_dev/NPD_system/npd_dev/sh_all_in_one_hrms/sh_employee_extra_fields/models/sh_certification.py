# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# Sh Certification


class ShCertification(models.Model):
    _name = "sh.certification"
    _description = "Sh Certification"

    cert_employee_id = fields.Many2one(
        'hr.employee', string='Profession Employee Reference', ondelete='cascade', index=True, copy=False)

    course = fields.Char(string='Course Name', required=True)
    level_completion = fields.Char(string='Score', required=True)
    comp_year = fields.Date(string="Qualification Year", required=True)
    certificate = fields.Binary("Certificates")
