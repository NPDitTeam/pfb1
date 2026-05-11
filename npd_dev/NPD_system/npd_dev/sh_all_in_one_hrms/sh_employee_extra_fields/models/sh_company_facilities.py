# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# Company Facilities


class ShCompanyFacilities(models.Model):
    _name = "sh.company.facilities"
    _description = 'Sh Company Facilities'

    name = fields.Char('Name', required=True)
