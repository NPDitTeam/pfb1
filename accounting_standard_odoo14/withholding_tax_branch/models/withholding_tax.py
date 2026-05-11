# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError

class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    branch_id = fields.Many2one('res.branch', string='Branch')


    @api.model 
    def default_get(self, field): 
        result = super(WithholdingTaxCert, self).default_get(field)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result