# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.constrains('name')
    def _check_partner_name(self):
        Partner = self.env["res.partner"]
        for rec in self:
            if not rec.name:
                continue
            duplicate = Partner.search(
                [
                    ("name", "=", rec.name),
                    ("id", "!=", rec.id),
                    ("parent_id", "=", False),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("ชื่อคู่ค้า '%s' มีอยู่แล้ว (ID %s)")
                    % (rec.name, duplicate.id)
                )
