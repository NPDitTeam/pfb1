# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError

class StockMove(models.Model):
	_inherit = 'stock.move'

	secondary_uom_id = fields.Many2one('uom.uom', compute='_quantity_secondary_compute', string="Secondary UOM", store=True)
	secondary_quantity = fields.Float('Secondary Qty', compute='_quantity_secondary_compute', digits="Product Unit of Measure", store=True)
	secondary_done_qty = fields.Float('Secondary Quantity Done', compute='_quantity_secondary_done_compute', digits='Product Unit of Measure', inverse='_quantity_secondary_done_set')
 

	@api.depends('product_id', 'product_uom_qty','secondary_uom_id','secondary_done_qty')
	def _quantity_secondary_compute(self):
		for order in self:
			if order.product_id.is_secondary_uom:
				order.secondary_uom_id = order.product_id.secondary_uom_id
				# uom_quantity = order.product_id.uom_id._compute_quantity(order.product_uom_qty, order.product_id.secondary_uom_id, rounding_method='HALF-UP')
				order.secondary_quantity = order.secondary_done_qty
			else:
				order.secondary_uom_id = False
				order.secondary_quantity = 0.0

	@api.depends('quantity_done', 'move_line_ids.qty_done',
		'move_line_ids.secondary_done_qty',
		'move_line_ids.secondary_uom_id', 
		'move_line_nosuggest_ids.qty_done', 
		'move_line_nosuggest_ids.secondary_done_qty',
		'move_line_nosuggest_ids.secondary_uom_id')
	def _quantity_secondary_done_compute(self):
		for move in self:
			if move.product_id.is_secondary_uom:
				if move._get_move_lines():
					quantity_done = 0
					for move_line in move._get_move_lines():
						quantity_done += move_line.secondary_done_qty #move_line.secondary_uom_id._compute_quantity(move_line.secondary_done_qty, move.secondary_uom_id, round=False)
				else: 
					quantity_done = move.quantity_done #move.product_id.uom_id._compute_quantity(move.quantity_done, move.product_id.secondary_uom_id, rounding_method='HALF-UP')
			else:
				quantity_done = 0.0
			move.secondary_done_qty = quantity_done
 
	def _quantity_secondary_done_set(self):
		quantity_done = self[0].secondary_done_qty  # any call to create will invalidate `move.quantity_done`
		for move in self:
			move_lines = move._get_move_lines()
			if not move_lines:
				if quantity_done:
					# do not impact reservation here
					move_line = self.env['stock.move.line'].create(dict(move._prepare_move_line_vals(), secondary_done_qty=quantity_done))
					move.write({'move_line_ids': [(4, move_line.id)]})
			elif len(move_lines) == 1:
				move_lines[0].secondary_done_qty = quantity_done
				move_lines[0].secondary_quantity = quantity_done
			else:
				raise UserError(_("Cannot set the done quantity from this stock move, work directly with the move lines."))

	def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
		res = super(StockMove, self)._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
		if res:
			if self.product_id.is_secondary_uom:
				res.update({
					'secondary_uom_id': self.secondary_uom_id and self.secondary_uom_id.id or False,
				})
			else:
				res.update({
					'secondary_uom_id': False
				})
			if quantity:
				if self.product_id.is_secondary_uom:
					uom_quantity = quantity
					uom_quantity_back_to_product_uom = quantity
					# uom_quantity = self.product_id.uom_id._compute_quantity(quantity, self.secondary_uom_id, rounding_method='HALF-UP')
					# uom_quantity_back_to_product_uom = self.secondary_uom_id._compute_quantity(uom_quantity, self.product_id.uom_id, rounding_method='HALF-UP')
					rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
					if float_compare(quantity, uom_quantity_back_to_product_uom, precision_digits=rounding) == 0:
						res = dict(res, secondary_quantity=uom_quantity)
					else:
						res = dict(res, secondary_quantity=uom_quantity, product_uom_id=self.product_id.uom_id.id)
		return res

	def _action_cancel_done(self):
		super(StockMove, self)._action_cancel_done()
		for move in self:
			if move.picking_id.picking_type_id.code in ['outgoing', 'internal']:
				for line in move.move_line_ids:
					if line.product_id.tracking == 'lot':
						stock_quant = self.env['stock.quant'].sudo().search(
							[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_id.id),('lot_id', '=', line.lot_id.id)])
						outgoing_quant = self.env['stock.quant'].sudo().search(
								[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_dest_id.id),('lot_id', '=', line.lot_id.id)])
						if stock_quant and outgoing_quant:
							outgoing_quant.secondary_quantity = outgoing_quant.secondary_quantity - line.secondary_quantity 
							stock_quant.secondary_quantity = stock_quant.secondary_quantity + line.secondary_quantity
						
						if line.location_dest_id.usage == 'customer':
							outgoing_quant = self.env['stock.quant'].sudo().search(
								[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_dest_id.id)])
							if outgoing_quant:
								old_qty = sum(outgoing_quant.mapped('secondary_quantity'))
								outgoing_quant.secondary_quantity = old_qty - move.secondary_quantity
					else:
						stock_quant = self.env['stock.quant'].sudo().search(
							[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_id.id)])
						outgoing_quant = self.env['stock.quant'].sudo().search(
								[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_dest_id.id)])
						if stock_quant and outgoing_quant:
							outgoing_quant.secondary_quantity = outgoing_quant.secondary_quantity - line.secondary_quantity 
							stock_quant.secondary_quantity = stock_quant.secondary_quantity + line.secondary_quantity
						
						if line.location_dest_id.usage == 'customer':
							outgoing_quant = self.env['stock.quant'].sudo().search(
								[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_dest_id.id)])
							if outgoing_quant:
								old_qty = sum(outgoing_quant.mapped('secondary_quantity'))
								outgoing_quant.secondary_quantity = old_qty - move.secondary_quantity
			elif move.picking_id.picking_type_id.code == 'incoming':
				for move_id in move:
					for line in move_id.move_line_ids:
						if line.lot_id:
							if line.product_id.tracking == 'lot':
								incoming_quant = self.env['stock.quant'].sudo().search(
									[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_dest_id.id),
									('lot_id', '=', line.lot_id.id)])
								incoming_customer_quant = self.env['stock.quant'].sudo().search(
									[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_id.id),
									('lot_id', '=', line.lot_id.id)])
								if incoming_quant:
									old_qty = sum(incoming_quant.mapped('secondary_quantity'))
									incoming_quant.secondary_quantity = old_qty - move.secondary_quantity
								if incoming_customer_quant:
									old_qty = sum(incoming_customer_quant.mapped('secondary_quantity'))
									incoming_customer_quant.secondary_quantity = old_qty + move.secondary_quantity
							else:
								incoming_quant = self.env['stock.quant'].sudo().search(
									[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_id.id),
									('lot_id', '=', line.lot_id.id)])
								if incoming_quant:
									old_qty = sum(incoming_quant.mapped('secondary_quantity'))
									incoming_quant.unlink()
									vals = {'product_id': move.product_id.id,
											'location_id': move.location_dest_id.id,
											'secondary_quantity': old_qty,
											'lot_id': line.lot_id.id,
											}
									self.env['stock.quant'].sudo().create(vals)
						else:
							incoming_quant = self.env['stock.quant'].sudo().search(
								[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_dest_id.id)])
							if incoming_quant:
								old_qty = sum(incoming_quant.mapped('secondary_quantity'))
								incoming_quant.secondary_quantity = old_qty - move.secondary_quantity
							incoming_customer_quant = self.env['stock.quant'].sudo().search(
								[('product_id', '=', move.product_id.id), ('location_id', '=', line.location_id.id)])
							if incoming_customer_quant:
								old_qty = sum(incoming_customer_quant.mapped('secondary_quantity'))
								incoming_customer_quant.secondary_quantity

	def _action_done(self,cancel_backorder=False):
		super(StockMove,self)._action_done(cancel_backorder=cancel_backorder)

		for move in self:
			for ml in move.move_line_ids:
				if move.picking_id.picking_type_id.code in ['outgoing','internal']:
					outgoing_quant = self.env['stock.quant'].sudo().search([('product_id','=',move.product_id.id),('location_id','=',ml.location_dest_id.id)])
					stock_quant = self.env['stock.quant'].sudo().search([('product_id','=',move.product_id.id),('location_id','=',ml.location_id.id)])
					if outgoing_quant:
						old_qty = outgoing_quant[0].secondary_quantity
						outgoing_quant[0].secondary_quantity = old_qty + move.secondary_quantity
					if stock_quant:
						old_qty = stock_quant[0].secondary_quantity
						stock_quant[0].secondary_quantity = old_qty - move.secondary_quantity
				if move.picking_id.picking_type_id.code == 'incoming':
						if ml.lot_id:
							if move.product_id.tracking == 'lot':
								incoming_quant = self.env['stock.quant'].sudo().search([('product_id','=',move.product_id.id),('location_id','=',ml.location_dest_id.id),('lot_id','=',ml.lot_id.id)])
								incoming_customer_quant = self.env['stock.quant'].sudo().search([('product_id','=',move.product_id.id),('location_id','=',ml.location_id.id),('lot_id','=',ml.lot_id.id)])
								if incoming_quant:
									old_qty = incoming_quant[0].secondary_quantity
									incoming_quant[0].secondary_quantity = old_qty + move.secondary_quantity
								if incoming_customer_quant:
									old_qty = incoming_customer_quant[0].secondary_quantity
									incoming_customer_quant[0].secondary_quantity = old_qty - move.secondary_quantity

						else:
							incoming_quant = self.env['stock.quant'].sudo().search([('product_id','=',move.product_id.id),('location_id','=',ml.location_dest_id.id)])
							if incoming_quant:
								old_qty = incoming_quant[0].secondary_quantity
								incoming_quant[0].secondary_quantity = old_qty +  move.secondary_quantity
							incoming_customer_quant = self.env['stock.quant'].sudo().search([('product_id','=',move.product_id.id),('location_id','=',ml.location_id.id)])
							if incoming_customer_quant:
								old_qty = incoming_customer_quant[0].secondary_quantity
								incoming_customer_quant[0].secondary_quantity = old_qty - move.secondary_quantity



class StockMoveLine(models.Model):
	_inherit = 'stock.move.line'

	secondary_uom_id = fields.Many2one('uom.uom', string="Secondary UOM",compute='secondary_qty_compute')
	secondary_quantity = fields.Float("Secondary Qty", digits="Product Unit of Measure")
	secondary_done_qty = fields.Float("Secondary Done Qty", digits="Product Unit of Measure")


	@api.depends('product_id','product_id.uom_id','product_uom_qty','qty_done','product_id.secondary_uom_id','secondary_done_qty','secondary_quantity')
	def secondary_qty_compute(self):
		for move_line in self:
			if move_line.product_id.is_secondary_uom:
				move_line.update({'secondary_uom_id' : move_line.product_id.secondary_uom_id})
			# 	uom_quantity = move_line.product_id.uom_id._compute_quantity(move_line.product_uom_qty or move_line.qty_done, move_line.product_id.secondary_uom_id, rounding_method='HALF-UP')
			# 	uom_done_quantity = move_line.product_id.uom_id._compute_quantity(move_line.qty_done, move_line.product_id.secondary_uom_id, rounding_method='HALF-UP')
			else:
				move_line.update({
					'secondary_uom_id' : move_line.product_id.secondary_uom_id,
					'secondary_quantity' : 0.0,
					'secondary_done_qty' : 0.0,
				})
				

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4::