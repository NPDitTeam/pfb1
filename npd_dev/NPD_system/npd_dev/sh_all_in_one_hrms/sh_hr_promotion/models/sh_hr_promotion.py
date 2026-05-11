# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_emp_hr_promotion = fields.Boolean(
        "Enable Employee Promotion", implied_group='sh_all_in_one_hrms.group_enable_emp_hr_promotion') 
    
# Sh Hr Overtime object
class ShHrPromotion(models.Model):
    _name = 'sh.hr.promotion'
    _description = 'Sh Hr Promotion'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference',
                       required=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee Reference', ondelete='cascade', index=True, copy=False)
    sh_contracts = fields.Many2one("hr.contract", "Contract")
    sh_previous_designation = fields.Many2one(
        'hr.job', string="Previous Designation")
    sh_new_designation = fields.Many2one('hr.job', string="New Designation")
    sh_promotion_type_id = fields.Many2one(
        'sh.promotion.types', string="Promotion Type")
    sh_promotion_date = fields.Datetime(
        'Promotion Date', default=lambda self: fields.Datetime.now())
    sh_description = fields.Text("Description")
    sh_new_salary = fields.Float("New Salary")
    sh_previous_salary = fields.Float("Previous Salary")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.sh_previous_designation = self.employee_id.job_id
            self.sh_contracts = self.employee_id.contract_id.id
            self.company_id = self.employee_id.company_id
            self.sh_previous_salary = self.employee_id.contract_id.wage


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_promotion_ids = fields.One2many(
        'sh.hr.promotion', 'employee_id', string='Promotion Line', copy=True, auto_join=True)
    pr_count = fields.Integer(
        'Promotions Count', compute='_compute_get_hr_count')

    def open_hr_promotion(self):
        pr = self.env['sh.hr.promotion'].search(
            [('employee_id', '=', self.id)])
        action = self.env.ref(
            'sh_all_in_one_hrms.sh_hr_promotion_request_view_actions_2').read()[0]
        action['context'] = {
            'domain': [('id', 'in', pr.ids)],
            'employee_id': self.id,
        }
        action['domain'] = [('id', 'in', pr.ids)]
        return action

    def _compute_get_hr_count(self):
        if self:
            for rec in self:
                rec.pr_count = 0
                pr = self.env['sh.hr.promotion'].search(
                    [('employee_id', '=', rec.id)])
                rec.pr_count = len(pr.ids)
