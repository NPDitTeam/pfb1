# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models
from odoo.exceptions import UserError,ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.constrains('name')
    def _check_partner_name(self):
        Partner = self.env["res.partner"]
        for rec in self:
            partner_id = Partner.search(
                [
                    ("name", "=", rec.name),
                ]
            )
            if len(partner_id) > 1:
                raise UserError(
                    _(
                        "{} Partner name already.".format(
                            rec.name
                        )
                    )
                )