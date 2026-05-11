# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

from odoo import models, fields


class srResUsers(models.Model):
	_inherit = "res.users"

	user_time_validity = fields.Boolean("user time validity")
	start_date = fields.Date("start date")
	end_date = fields.Date("end date")
	message = fields.Char("messages")
