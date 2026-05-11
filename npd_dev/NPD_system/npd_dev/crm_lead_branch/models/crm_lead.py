from odoo import models, fields, api

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    branch_id = fields.Many2one('res.branch', string='Branch')

    @api.model
    def create(self, vals):
        user = self.env.user
        if user.branch_id:
            vals['branch_id'] = user.branch_id.id
        return super(CrmLead, self).create(vals)

    def write(self, vals):
        user = self.env.user
        if user.branch_id:
            vals['branch_id'] = user.branch_id.id
        return super(CrmLead, self).write(vals)
