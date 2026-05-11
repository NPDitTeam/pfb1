# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    fax = fields.Char(
        related="partner_id.fax", string="Fax", readonly=False
    )
