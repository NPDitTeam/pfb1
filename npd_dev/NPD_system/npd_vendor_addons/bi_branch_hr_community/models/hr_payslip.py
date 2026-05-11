from odoo import api, fields, models, _

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    branch_id = fields.Many2one('res.branch', string='Branch')

    @api.model
    def default_get(self, flds):
        """ Override to get default branch from employee """
        result = super(HrPayslip, self).default_get(flds)
        employee_id = self.env['hr.employee'].browse(self._context.get('active_id'))
        result['branch_id'] = employee_id.branch_id.id
        return result

    @api.onchange('employee_id')
    def get_branch(self):
        if self.employee_id:
            if self.employee_id.branch_id:
                self.update({'branch_id':self.employee_id.branch_id})
            else:
                self.update({'branch_id': False})