# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_multi_user = fields.Boolean('Display multi users in task ?')


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    sh_multi_user = fields.Boolean('Display multi users in task ?',
                                   related='company_id.sh_multi_user',
                                   readonly=False)
