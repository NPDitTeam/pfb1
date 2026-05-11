# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta

class AccountAdvance(models.Model):
    _inherit = "account.advance"

    end_date = fields.Date('End Date')

    def open(self):
        due_date_clear = self.env.company.due_date_clear
        if self.end_date:
            today = self.end_date
        else:
            today = datetime.today()
            self.end_date = datetime.today()
        date_clear = today + timedelta(days=+due_date_clear)
        self.due_date_clear = date_clear
        super(AccountAdvance,self).open()