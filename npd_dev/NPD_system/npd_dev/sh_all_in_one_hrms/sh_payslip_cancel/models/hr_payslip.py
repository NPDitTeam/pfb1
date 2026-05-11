# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models
from odoo.tools.safe_eval import safe_eval as eval
from odoo.exceptions import ValidationError


class HRPayslip(models.Model):
    """ Inherited hr.payslip to add additonal field"""
    _inherit = 'hr.payslip'

    refunded_payslip_id = fields.Many2one(
        'hr.payslip',
        string='Refunded Payslip',
        readonly=True
    )

    def refund_sheet(self):
        res = super(HRPayslip, self).refund_sheet()
        self.write({'refunded_payslip_id': eval(
            res['domain'])[0][2][0] or False})
        return res

    def action_payslip_cancel(self):
        for record in self:
            if record.refunded_payslip_id and record.refunded_payslip_id.state != 'cancel':
                raise ValidationError(
                    "Refunded Payslip needs to be in cancel state to cancel this Orinal one")

            if record.move_id.state == 'draft':
                record.move_id.button_cancel()
                record.move_id.unlink()
            elif record.move_id.state == 'posted':
                record.move_id.button_draft()
                record.move_id.button_cancel()
                record.move_id = False
        self.write({'state': 'cancel'})
