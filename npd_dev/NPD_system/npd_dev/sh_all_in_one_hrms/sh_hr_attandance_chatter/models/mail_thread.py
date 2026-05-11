# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models


class MailThread(models.Model):
    _name = 'hr.attendance'
    _inherit = ['hr.attendance', 'mail.thread']
