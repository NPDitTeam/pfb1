from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    branch_id = fields.Many2one('res.branch', string='Branch')
    end_date = fields.Date(compute='_fund_balance')

    @api.onchange("end_date")
    def _fund_balance(self):
        for record1 in self:
            record1.end_date = '2023-03-09'

        users = self.env['res.users'].search([])
        for user in users:
            if user.branch_id:
                # branches = self.env['res.branch'].search([('id', '=', int(user.branch_id))])
                self.env.cr.execute(
                    'update public.crm_lead set branch_id=%s where user_id=%s',
                    (int(user.branch_id), int(user.id)))

                # print(f"Branch ID: {user.id}, Branch Name: {user.branch_id}")


