# -*- coding: utf-8 -*-
import calendar

from odoo import tools, api, models, _, fields
from odoo.exceptions import UserError
from odoo.tools import config
from odoo.exceptions import ValidationError
import datetime as dt

from odoo.http import request


class CreateStock(models.Model):
    _name = "salon.stock"

    # @api.multi
    def write(self, vals):
        # overriding the write method of appointment model
        res = super(CreateStock, self).write(vals)
        print("Test write function")
        # do as per the need
        return res

