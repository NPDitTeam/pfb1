# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class HrContract(models.Model):
    _inherit = 'hr.contract'

    sh_contract_department_policy = fields.Html(related="department_id.sh_department_policy",
                                                string="Department Policy",
                                                )

    sh_contract_company_policy = fields.Html(related="company_id.sh_policy",
                                             string="Company Policy",
                                             )
