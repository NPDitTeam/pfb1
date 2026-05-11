# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.model
    def create(self, vals):
        order_sequence = vals.get("order_sequence") or self.env.context.get(
            "order_sequence"
        )
        if not order_sequence and vals.get("name", "/") == "/":
            vals["name"] = self.env["ir.sequence"].next_by_code("purchase.rfq", sequence_date=vals.get("order_date", None)) or "/"
        elif vals.get("rfq_number") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("purchase.order", sequence_date=vals.get("order_date", None)) or "/"
        return super().create(vals)

    def _prepare_order_from_rfq(self):
        return {
            "name": self.env["ir.sequence"].next_by_code("purchase.order", sequence_date=self.order_date) or "/",
            "order_sequence": True,
            "quote_id": self.id,
            "partner_ref": self.partner_ref,
        }