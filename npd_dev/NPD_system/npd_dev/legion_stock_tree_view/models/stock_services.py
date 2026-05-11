# -*- coding: utf-8 -*-
import calendar

from odoo import tools, api, models, _, fields
from odoo.exceptions import UserError
from odoo.tools import config
from odoo.exceptions import ValidationError
import datetime as dt


class CreateStock(models.Model):
    _name = "salon.services"

    service_name = fields.Char(string='Service')
    service_price = fields.Integer(string='Service Amount')
