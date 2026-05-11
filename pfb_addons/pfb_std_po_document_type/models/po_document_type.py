# -*- coding: utf-8 -*-
import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)

class po_document_type(models.Model):
    _name = 'po.document.type'
    name = fields.Char(string="Document", required=True)

class purchase_request(models.Model):
    _inherit = "purchase.request"
    document_type = fields.Many2one('po.document.type', string='Document Type')

class purchase_order(models.Model):
    _inherit = "purchase.order"
    document_type = fields.Many2one('po.document.type', string='Document Type')
    department_id = fields.Many2one('hr.department', string='Department')


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = "purchase.request.line.make.purchase.order"
    document_type = fields.Many2one('po.document.type', string='Document Type')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get("active_model", False) != "purchase.request":
            return res
        for data in self.env["purchase.request"].browse(self._context.get("active_ids", [])):
            if data.document_type.id:
                res["document_type"] = data.document_type.id or 0
        return res


    def make_purchase_order(self):
        res = super().make_purchase_order()
        for data in self:
            document_type_id = data.document_type.id
            domain = res.get('domain') or ''
            for po in self.env['purchase.order'].search(domain):
                po.write({'document_type': document_type_id})
        return res


