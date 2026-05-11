from odoo import models, fields, api, _


class CashType(models.Model):
    _name = 'cash.type'
    _description = _('cash.type')
    

    name = fields.Char(string=_('Cash Type Name'),required=True)
    value = fields.Float(string=_('Value'), digits='Account')
    active = fields.Boolean(string=_('active'), default=True)