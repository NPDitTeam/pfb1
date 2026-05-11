# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MergePickingWizardLine(models.TransientModel):
    _name = 'sh.merge.picking.wizard.line'
    _description = 'Merge Picking Wizard Line'

    merge_line_id = fields.Many2one(
        'sh.merge.picking.order.wizard', string='Merge Picking Wizard Line')
    qty = fields.Float(string='Quantity')
    product_id = fields.Many2one('product.product', string='Product')
    picking_order_line_id = fields.Many2one(
        "stock.move", string="Stock Move Line")
    picking_order_id = fields.Many2one("stock.picking", string="Picking Order")
    qty_available = fields.Float('Quantity On Hand')


class ShMergePickingOrderWizard(models.TransientModel):
    _name = "sh.merge.picking.order.wizard"
    _description = "Merge Picking Order Wizard"

    partner_id = fields.Many2one(
        "res.partner", string="Contact")
    picking_order_id = fields.Many2one(
        "stock.picking", string="Existing Picking Order")
    picking_order_ids = fields.Many2many(
        "stock.picking", string="Picking Orders")
    location_id = fields.Many2one('stock.location', 'Source Location')
    location_dest_id = fields.Many2one(
        'stock.location', 'Destination Location')
    merge_type = fields.Selection([
        ("nothing_new", "New Order and Do Nothing with selected picking orders"),
        ("cancel_new", "New Order and Cancel selected picking orders"),
        ("remove_new", "New Order and Remove selected picking orders"),
        ("nothing_existing", "Existing Order and Do Nothing with selected picking orders"),
        ("cancel_existing", "Existing Order and Cancel selected picking orders"),
        ("remove_existing", "Existing Order and Remove selected picking orders"),
    ], string="Merge Type")
    picking_type_code = fields.Selection([
        ('incoming', 'Receipts'),
        ('outgoing', 'Delivery Orders'),
        ('internal', 'Internal Transfers'),
    ])
    merge_line_ids = fields.One2many(
        'sh.merge.picking.wizard.line', 'merge_line_id', string='Merge Quote Wizard')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    sh_is_merge_chatter_picking = fields.Boolean(
        string=" Is Merged Chatter Message", default=True)
    
    sh_is_qty_available_picking = fields.Boolean(
        string=" Is Qty available", default=False)

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        if self:
            self.picking_order_id = False

    def action_merge_picking_order(self):
        order_list = []
        picking_order = False
        if self and self.picking_order_ids:
            if self.picking_order_id:
                picking_order = self.picking_order_id
                order_list.append(self.picking_order_id.id)
                order_line_vals = {"picking_id": self.picking_order_id.id}
                for order in self.picking_order_ids.filtered(lambda o: o.id != self.picking_order_id.id):
                    if order.move_ids_without_package:
                        for line in order.move_ids_without_package:
                            for merge in self.merge_line_ids:
                                if merge.picking_order_line_id.id == line.id:
                                    if self.company_id.sh_stock_sub_merge_qty:
                                        if merge.qty <= line.product_uom_qty:
                                            order_line_vals['product_uom_qty'] = merge.qty
                                            SO = line.product_uom_qty - merge.qty

                                            if SO > 0:
                                                line.product_uom_qty = SO
                                            else:
                                                line.copy(
                                                    default=order_line_vals)
                                                line.unlink()
                                        else:
                                            raise UserError(
                                                _("%s Quantity is can't be more than Transfers (%s) Lines Quantity (%s)") % (merge.product_id.name, merge.picking_order_id.name, line.product_uom_qty))
                                    else:
                                        if merge.qty > line.product_uom_qty:
                                            raise UserError(
                                                _("%s Quantity is can't be more than Transfers (%s) Lines Quantity (%s)") % (merge.product_id.name, merge.picking_order_id.name, line.product_uom_qty))
                                        else:
                                            order_line_vals['product_uom_qty'] = merge.qty

                            if line.exists():
                                line.copy(default=order_line_vals)
                    # finally cancel or remove order
                pickings = []
                for picking in self.env['stock.picking'].sudo().browse(self.env.context.get('active_ids')):
                    if picking.name not in pickings:
                        pickings.append(picking.name)
                    if self.merge_type == "cancel_existing":
                        picking.sudo().action_cancel()
                    elif self.merge_type == "remove_existing":
                        picking.sudo().unlink()

                if self.env.company.notify_in_chatter:
                    message = '<p>This Existing picking order has been updated from '
                    message += ','.join(pickings) + str('</p>')
                    self.env['mail.message'].sudo().create({
                        'subtype_id': self.env.ref('mail.mt_comment').id,
                        'date': fields.Datetime.now(),
                        'email_from': self.env.user.partner_id.email_formatted,
                        'message_type': 'comment',
                        'model': 'stock.picking',
                        'res_id': self.picking_order_id.id,
                        'record_name': self.picking_order_id.name,
                        'body': message
                    })
            else:
                first_picking_code = self.picking_order_ids[0].picking_type_id.id
                picking_vals = {}
                picking_vals.update({
                    "location_id": self.location_id.id,
                    "location_dest_id": self.location_dest_id.id,
                    "picking_type_id": first_picking_code,
                    "scheduled_date": fields.Datetime.now(),
                    "user_id": self.env.user.id,
                })
                if self.partner_id:
                    picking_vals.update({
                        "partner_id": self.partner_id.id,
                    })
                created_picking_order = self.env["stock.picking"].sudo().create(
                    picking_vals)
                if created_picking_order:
                    picking_order = created_picking_order
                    order_list.append(created_picking_order.id)
                    order_line_vals = {"picking_id": created_picking_order.id}
                    pickings = []
                    for order in self.picking_order_ids:
                        if order.name not in pickings:
                            pickings.append(order.name)
                        if order.move_ids_without_package:
                            for line in order.move_ids_without_package:
                                for merge in self.merge_line_ids:
                                    if merge.picking_order_line_id.id == line.id:
                                        if self.company_id.sh_stock_sub_merge_qty:
                                            if merge.qty <= line.product_uom_qty:
                                                order_line_vals['product_uom_qty'] = merge.qty
                                                SO = line.product_uom_qty - merge.qty

                                                if SO > 0:
                                                    line.product_uom_qty = SO
                                                else:
                                                    merged_line = line.copy(
                                                        default=order_line_vals)
                                                    line.unlink()
                                            else:
                                                raise UserError(
                                                    _("%s Quantity is can't be more than Transfers (%s) Lines Quantity (%s)") % (merge.product_id.name, merge.picking_order_id.name, line.product_uom_qty))
                                        else:
                                            if merge.qty > line.product_uom_qty:
                                                raise UserError(
                                                    _("%s Quantity is can't be more than Transfers (%s) Lines Quantity (%s)") % (merge.product_id.name, merge.picking_order_id.name, line.product_uom_qty))
                                            else:
                                                order_line_vals['product_uom_qty'] = merge.qty

                                if line.exists():
                                    line.copy(default=order_line_vals)
                        # finally cancel or remove order
                        if self.merge_type == "cancel_new":
                            order.sudo().action_cancel()
                            order_list.append(order.id)
                        elif self.merge_type == "remove_new":
                            order.sudo().action_cancel()
                            order.sudo().unlink()
                    if self.env.company.notify_in_chatter:
                        message = '<p>This picking order has been created from '
                        message += ','.join(pickings) + str('</p>')
                        self.env['mail.message'].sudo().create({
                            'subtype_id': self.env.ref('mail.mt_comment').id,
                            'date': fields.Datetime.now(),
                            'email_from': self.env.user.partner_id.email_formatted,
                            'message_type': 'comment',
                            'model': 'stock.picking',
                            'res_id': created_picking_order.id,
                            'record_name': created_picking_order.name,
                            'body': message
                        })
            # For Merge Chatter Message
            if picking_order and self.sh_is_merge_chatter_picking:
                self.env['sh.select.model.record.wizard'].sh_merge_chatter_message(
                    record=picking_order)

            if order_list:
                return {
                    "name": _("Picking Orders"),
                    "domain": [("id", "in", order_list)],
                    "view_type": "form",
                    "view_mode": "tree,form",
                    "res_model": "stock.picking",
                    "view_id": False,
                    "type": "ir.actions.act_window",
                }

    @api.model
    def default_get(self, fields):
        rec = super(ShMergePickingOrderWizard, self).default_get(fields)
        active_ids = self._context.get("active_ids")
        line_list = []

        if not active_ids:
            raise UserError(
                _("Programming error: wizard action executed without active_ids in context."))

        if len(self._context.get("active_ids", [])) < 2:
            raise UserError(
                _("Please Select atleast two pickings to perform merge operation."))

        picking_orders = self.env["stock.picking"].browse(active_ids)

        if any(order.state not in ["draft", "waiting", "confirmed", "assigned"] for order in picking_orders):
            raise UserError(
                _("You can only merge picking orders which are in Draft/Waiting/Ready state"))
            
        # check stock dependency
        stock_app = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'stock')], limit=1)
        if stock_app.state != 'installed':
            sh_is_qty_available_picking = False
        else:
            sh_is_qty_available_picking = True

        if len(picking_orders.ids) > 0:
            first_picking_code = picking_orders[0].picking_type_code
            rec.update({
                'picking_type_code': first_picking_code
            })
            if first_picking_code == 'incoming':
                if self.env.ref('stock.stock_location_suppliers'):
                    rec.update({
                        'location_id': self.env.ref('stock.stock_location_suppliers').id,
                    })
            elif first_picking_code == 'outgoing':
                if self.env.ref('stock.stock_location_customers'):
                    rec.update({
                        'location_dest_id': self.env.ref('stock.stock_location_customers').id
                    })
            for order in picking_orders:
                if order.picking_type_code != first_picking_code:
                    raise UserError(
                        _("You can only merge picking orders which are in same operation type. "))
        if self.env.company.merge_type:
            rec.update({
                'merge_type': self.env.company.merge_type
            })
        for res in picking_orders:
            if res.move_ids_without_package:
                lines = res.mapped('move_ids_without_package')
                if lines:
                    for line in lines:
                        line_vals = {
                            'product_id': line.product_id.id,
                            'qty': line.product_uom_qty,
                            'picking_order_id': res.id,
                            'picking_order_line_id': line.id,
                            'qty_available': line.product_id.qty_available if sh_is_qty_available_picking else None,

                        }
                        line_list.append((0, 0, line_vals))

        rec.update({
            "partner_id": picking_orders[0].partner_id.id if picking_orders[0].partner_id else False,
            "picking_order_ids": [(6, 0, picking_orders.ids)],
            "merge_line_ids": line_list,
            'sh_is_qty_available_picking': sh_is_qty_available_picking or False,
        })
        return rec
