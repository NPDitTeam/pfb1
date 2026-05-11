# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import  fields, models

class OtConfigWeekday(models.Model):

    _name = 'sh.overtime.config.weekday'

    from_hour = fields.Float(string = "From hour")
    to_hour = fields.Float(string = "To hour")
    hours_rate_multiplication = fields.Float(string = "Multiplies (X) hour rate")
    