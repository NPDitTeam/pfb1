# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ResCompany(models.Model):
    _inherit = "res.company"

    due_date_clear = fields.Integer('Due Date Clear')

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    due_date_clear = fields.Integer(  
        related="company_id.due_date_clear",string='Due Date Clear',readonly=False,)