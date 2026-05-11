# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _get_branch_domain(self):
        return [('company_id','=',self.env.company.id)]

    branch_ids = fields.Many2many('res.branch',string="Allowed Branch", domain=lambda self:self._get_branch_domain())
    branch_id = fields.Many2one('res.branch', string= 'Branch')

    def write(self, values):
        if 'branch_id' in values or 'branch_ids' in values:
            self.env['ir.model.access'].call_cache_clearing_methods()
        user = super(ResUsers, self).write(values)
        return user
