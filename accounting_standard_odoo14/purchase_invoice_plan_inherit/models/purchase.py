# Copyright 2019 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from dateutil.relativedelta import relativedelta
import json
from lxml import etree as etree
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from psycopg2 import sql
from odoo.tools.float_utils import float_compare, float_round


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    date_start_plan = fields.Date('Start Date')

    def re_calculate_invoice_plan(self):
        self.ensure_one()
        if not self.date_start_plan:
            raise ValidationError(
                _("Please select a date in invoice plan")
            )
        for line in self.invoice_plan_ids:
            # next date
            date = self.date_start_plan
            if not line.invoiced:
                installment_date = self._next_date(
                    date, line.date_next, 'date'
                )
                date = installment_date
                line.sudo().write({'plan_date': date})
        return True

    def create_invoice_plan(
            self, num_installment, installment_date, interval, interval_type
    ):
        res = super(PurchaseOrder, self).create_invoice_plan(num_installment, installment_date, interval, interval_type)
        query = sql.SQL("UPDATE purchase_invoice_plan pip SET plan_date = NULL WHERE pip.purchase_id = %s")
        self.sudo()._cr.execute(query, [self.id])
        return res

    @api.model
    def fields_view_get(
            self, view_id=None, view_type="form", toolbar=False, submenu=False
    ):
        res = super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        group = "purchase_invoice_plan_inherit.account_invoice_plan_po"
        if view_type == "form":
            doc = etree.XML(res["arch"])
            for node in doc.xpath("//field[@name='invoice_plan_ids']"):
                if self.env.user.has_group(group):
                    # and po.state not in ['draft']
                    node.set("readonly", "0")
                    node.set("force_save", "0")
                    modifiers = json.loads(node.get("modifiers"))
                    modifiers["readonly"] = False
                    modifiers["force_save"] = 0
                    node.set("modifiers", json.dumps(modifiers))
            res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    def action_create_invoice(self):
        for order in self:
            for line in order.order_line:
                if line.product_id and not line.is_deposit and line.price_subtotal == 0:
                    line.qty_to_invoice = -1
                if line.is_deposit:
                    line.qty_to_invoice = -1
        res = super(PurchaseOrder, self).action_create_invoice()
        return res


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line()
        print(res)
        if self.is_deposit:
            if self.order_id.invoice_plan_ids:
                for line in self.order_id.invoice_plan_ids:
                    if line.to_invoice:
                        res["price_unit"] = (res["price_unit"] * (line.percent / 100)) * -1
                        res["quantity"] = 1
            res["quantity"] = 1

        if self.product_id and self.price_subtotal == 0:
            if self.order_id.invoice_plan_ids:
                for line in self.order_id.invoice_plan_ids:
                    if line.to_invoice:
                        res["price_unit"] = (self.price_unit * (line.percent / 100)) * -1
            res["quantity"] = 1
        return res
