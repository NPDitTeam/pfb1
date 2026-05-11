# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.exceptions import UserError, ValidationError
from odoo.addons import decimal_precision as dp


class AccountMove(models.Model):
	_inherit = 'account.move'

	def button_cancel(self):
		res = super(AccountMove, self).button_cancel()
		self.env['account.asset.asset'].sudo().search([('invoice_id', 'in', self.ids)]).write({'active': False})
		return res


class AccountInvoiceLine(models.Model):
	_inherit = 'account.move.line'

	asset_category_id = fields.Many2one('account.asset.category', string='Asset Category', store=True,related="product_id.asset_category_id")
	asset_start_date = fields.Date(string='Asset Start Date', compute='_get_asset_date', readonly=True, store=True)
	asset_end_date = fields.Date(string='Asset End Date', compute='_get_asset_date', readonly=True, store=True)
	asset_mrr = fields.Float(string='Monthly Recurring Revenue', compute='_get_asset_date', readonly=True, digits=dp.get_precision('Account'), store=True)
	
	@api.depends('asset_category_id', 'move_id.invoice_date')
	def _get_asset_date(self):
		for ml in self:
			ml.asset_mrr = 0
			ml.asset_start_date = False
			ml.asset_end_date = False
			cat = ml.asset_category_id
			if cat:
				if cat.method_number == 0 or cat.method_period == 0:
					raise UserError(_('The number of depreciations or the period length of your asset category cannot be null.'))
				months = cat.method_number * cat.method_period
				if ml.move_id.move_type in ['out_invoice', 'out_refund']:
					ml.asset_mrr = ml.price_subtotal / months
				if ml.move_id.invoice_date:
					start_date = datetime.strptime(str(ml.move_id.invoice_date), DF).replace(day=1)
					end_date = (start_date + relativedelta(months=months, days=-1))
					ml.asset_start_date = start_date.strftime(DF)
					ml.asset_end_date = end_date.strftime(DF)

	def asset_create(self):
		if self.asset_category_id:
			vals = {
				'name': self.name,
				'code': self.move_id.number or False,
				'category_id': self.asset_category_id.id,
				'value': self.price_subtotal,
				'partner_id': self.move_id.partner_id.id,
				'company_id': self.move_id.company_id.id,
				'currency_id': self.move_id.company_currency_id.id,
				'date': self.move_id.invoice_date,
				'move_id': self.move_id.id,
			}
			changed_vals = self.env['account.asset.asset'].onchange_category_id_values(vals['category_id'])
			vals.update(changed_vals['value'])
			asset = self.env['account.asset.asset'].create(vals)
			if self.asset_category_id.open_asset:
				asset.validate()
		return True

	@api.onchange('asset_category_id')
	def onchange_asset_category_id(self):
		if self.move_id.move_type == 'out_invoice' and self.asset_category_id:
			self.account_id = self.asset_category_id.account_asset_id.id
		elif self.move_id.move_type == 'in_invoice' and self.asset_category_id:
			self.account_id = self.asset_category_id.account_asset_id.id

	@api.onchange('uom_id')
	def _onchange_uom_id(self):
		result = super(AccountInvoiceLine, self)._onchange_uom_id()
		self.onchange_asset_category_id()
		return result

	@api.onchange('product_id')
	def _onchange_product_id(self):
		vals = super(AccountInvoiceLine, self)._onchange_product_id()
		for line in self:
			if line.product_id:
				if line.move_id.move_type == 'out_invoice':
					line.asset_category_id = line.product_id.product_tmpl_id.deferred_revenue_category_id
				elif line.move_id.move_type == 'in_invoice':
					line.asset_category_id = line.product_id.product_tmpl_id.asset_category_id
		return vals

	def get_invoice_line_account(self, type, product, fpos, company):
		return product.asset_category_id.account_asset_id or super(AccountInvoiceLine, self).get_invoice_line_account(type, product, fpos, company)
