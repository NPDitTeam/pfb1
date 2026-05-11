# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models


class SHPayslipRUN(models.Model):
    _inherit = 'hr.payslip.run'

    sh_payslip_count = fields.Integer(
        string='Payslip Count', compute='_compute_payslip_count')

    def _compute_payslip_count(self):
        for record in self:
            record.sh_payslip_count = 0
            payslips = self.env['hr.payslip'].search(
                [('id', 'in', record.slip_ids.ids)], limit=None)
            record.sh_payslip_count = len(payslips.ids)

    def action_view_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payslips',
            'view_mode': 'tree,form',
            'res_model': 'hr.payslip',
            'domain': [('id', 'in', self.slip_ids.ids)],
        }
