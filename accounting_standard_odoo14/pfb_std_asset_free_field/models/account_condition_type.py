from odoo import fields, models, api


class AccountConditionType(models.Model):
    _name = 'account.condition.type'
    _description = 'Description'

    name = fields.Char('name')
    asset_id = fields.One2many(
        comodel_name='account.asset',
        inverse_name='std_condition_type_id',
        string='Asset',
        required=True)
