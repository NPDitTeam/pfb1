# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    sh_department_policy = fields.Html(
        string="Department Policy",
    )
