
# from odoo import fields, models, api, _
#
#
# class ResCurrency(models.Model):
#     _inherit = 'account.advance.clear'
#
#
#     currency_id = fields.Many2one(
#         'res.currency',
#         string='Currency',
#         readonly=True,
#         store=True,
#         domain="[('name', '=', 'THB')]",
#     )



# from odoo import models, fields, api
# from odoo.exceptions import ValidationError
#
# class ResCurrency(models.Model):
#     _inherit = 'res.currency'
#
#     is_main_currency = fields.Boolean(string='Main Currency', default=False)
#
#     @api.constrains('is_main_currency')
#     def _check_main_currency(self):
#         for record in self:
#             if record.is_main_currency:
#                 other_currencies = self.search([('id', '!=', record.id)])
#                 other_currencies.write({'is_main_currency': False})
#                 company = self.env['res.company'].search([])
#                 for comp in company:
#                     if comp.currency_id != record:
#                         comp.currency_id = record
#
#     def write(self, vals):
#         if 'is_main_currency' in vals and vals['is_main_currency']:
#             self.search([]).write({'is_main_currency': False})
#             company = self.env['res.company'].search([])
#             for comp in company:
#                 if comp.currency_id != self:
#                     comp.currency_id = self
#         return super(ResCurrency, self).write(vals)
#
#     @api.model
#     def create(self, vals):
#         if vals.get('is_main_currency', False):
#             self.search([]).write({'is_main_currency': False})
#         return super(ResCurrency, self).create(vals)
#
#     def write(self, vals):
#         if 'is_main_currency' in vals and vals['is_main_currency']:
#             self.search([]).write({'is_main_currency': False})
#         return super(ResCurrency, self).write(vals)
#
#
#
#
#
