# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    notification_bool = fields.Boolean("Overdue Notification ?", related='company_id.notification_bool',
        readonly=False)
    overdue_days = fields.Integer("Overdue Days",related='company_id.overdue_days',
        readonly=False)
    start_date_bool = fields.Boolean('Start Date Notification ?',related='company_id.start_date_bool',
        readonly=False)
    start_days = fields.Integer('Start Date Days',related='company_id.start_days',
        readonly=False)
