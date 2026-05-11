# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context, format_date, OrderedSet



class InventoryLine(models.Model):
	_inherit = "stock.inventory.line"

	def _check_no_duplicate_line(self):
		return []


	@api.depends('product_qty', 'theoretical_qty')
	def _compute_difference(self):
		for line in self:
			line.difference_qty = line.product_qty - abs(line.theoretical_qty)




