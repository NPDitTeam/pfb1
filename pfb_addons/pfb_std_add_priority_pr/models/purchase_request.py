from odoo import _, api, fields, models


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)


class PurchaseRequestLine(models.Model):
    _inherit = "purchase.request.line"

    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)
