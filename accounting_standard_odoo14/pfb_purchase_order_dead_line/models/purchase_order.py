# Copyright 2017-2020 Forgeflow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

   
    order_date = fields.Date(
        string="Order Date",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    lead_time = fields.Integer('Lead Time',compute="_compute_lead_time", compute_sudo=True, store=True, readonly=True)

    @api.depends('date_planned','date_order')
    def _compute_lead_time(self):
        for po in self:
            lead_day = 0
            if po.date_planned and po.date_order:
                diff = po.date_planned - po.date_order
                lead_day = diff.days
            po.lead_time = lead_day

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    product_category_id = fields.Many2one(related='product_id.categ_id',store=True)
    order_date = fields.Date(related='order_id.order_date', string='Order Date', readonly=True,store=True)
    date_approve = fields.Datetime(related='order_id.date_approve', string='Confirm Date', readonly=True,store=True)
    lead_time = fields.Integer('Lead Time',related='order_id.lead_time',store=True)
    payment_term_id = fields.Many2one(related='order_id.payment_term_id',store=True)
    destination = fields.Char('Destination')