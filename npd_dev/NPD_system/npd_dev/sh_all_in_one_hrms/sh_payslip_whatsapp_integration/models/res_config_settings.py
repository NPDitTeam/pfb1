# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    payroll_information_in_message = fields.Boolean(
        "Payroll Information in message?", default=True)
    payroll_signature = fields.Boolean("Signature?", default=True)
    payroll_send_pdf_in_message = fields.Boolean(
        "Send Report URL in message?", default=True)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    payroll_information_in_message = fields.Boolean(
        related="company_id.payroll_information_in_message", string="Payroll Information in message?", readonly=False)
    payroll_signature = fields.Boolean(
        related="company_id.payroll_signature", string="Signature?", readonly=False)
    payroll_send_pdf_in_message = fields.Boolean(
        related="company_id.payroll_send_pdf_in_message", string="Send Report URL in message?", readonly=False)
