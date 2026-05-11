
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            vals["name"] = self._get_default_name(date=vals.get('date_start'))
        request = super(PurchaseRequest, self).create(vals)
        if vals.get("assigned_to"):
            partner_id = self._get_partner_id(request)
            request.message_subscribe(partner_ids=[partner_id])
        return request

    @api.model
    def _get_default_name(self, date=None):
        return self.env["ir.sequence"].next_by_code("purchase.request", sequence_date=date)
