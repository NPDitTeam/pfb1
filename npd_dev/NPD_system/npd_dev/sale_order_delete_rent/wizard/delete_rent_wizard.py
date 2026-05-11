# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class DeleteRentOrderWizard(models.TransientModel):
    _name = 'delete.rent.order.wizard'
    _description = 'Delete Rent Orders Wizard'

    confirm_delete = fields.Boolean(
        string='I confirm to delete all Rent orders',
        default=False,
        help='Check this box to confirm deletion of all Rent type Sale Orders'
    )
    
    order_count = fields.Integer(
        string='Number of Orders to Delete',
        compute='_compute_order_count',
        readonly=True
    )
    
    preview_ids = fields.Many2many(
        'sale.order',
        string='Orders to be Deleted',
        compute='_compute_preview_orders'
    )

    @api.depends('confirm_delete')
    def _compute_order_count(self):
        for wizard in self:
            orders = self.env['sale.order'].search([('pfb_so_type', '=', 'rent')])
            wizard.order_count = len(orders)

    @api.depends('confirm_delete')
    def _compute_preview_orders(self):
        for wizard in self:
            orders = self.env['sale.order'].search([('pfb_so_type', '=', 'rent')], limit=100)
            wizard.preview_ids = orders

    def action_delete_rent_orders(self):
        """Delete all Rent type Sale Orders with related documents"""
        self.ensure_one()
        
        if not self.confirm_delete:
            raise UserError(_('Please confirm the deletion by checking the confirmation box.'))
        
        orders = self.env['sale.order'].search([('pfb_so_type', '=', 'rent')])
        
        if not orders:
            raise UserError(_('No Rent type Sale Orders found to delete.'))
        
        deleted_count = 0
        error_orders = []
        
        # Collect order info before processing
        order_data = [(order.id, order.name) for order in orders]
        
        for order_id, order_name in order_data:
            try:
                # Use new cursor for each order to isolate transactions
                with self.env.cr.savepoint():
                    order = self.env['sale.order'].browse(order_id)
                    
                    if not order.exists():
                        continue
                    
                    # Process Invoices
                    for inv in order.invoice_ids:
                        if inv.exists():
                            try:
                                if inv.state == 'posted':
                                    inv.button_draft()
                                    inv.button_cancel()
                                elif inv.state not in ['draft', 'cancel']:
                                    inv.button_cancel()
                                inv.with_context(force_delete=True).unlink()
                            except Exception as e:
                                _logger.warning("Error deleting invoice for %s: %s", order_name, str(e))

                    # Process Stock Pickings
                    for pick in order.picking_ids:
                        if pick.exists():
                            try:
                                if pick.state == 'done':
                                    pick.action_cancel()
                                elif pick.state not in ['draft', 'cancel']:
                                    pick.action_cancel()
                                pick.with_context(force_delete=True).unlink()
                            except Exception as e:
                                _logger.warning("Error deleting picking for %s: %s", order_name, str(e))
                    
                    # Cancel and Delete Sale Order
                    if order.state != 'cancel':
                        order.action_cancel()
                    
                    order.with_context(force_delete=True).unlink()
                    deleted_count += 1
                    _logger.info("Successfully deleted Rent order: %s", order_name)
                    
            except Exception as e:
                error_orders.append({
                    'name': order_name,
                    'error': str(e)
                })
                _logger.error("Error deleting order %s: %s", order_name, str(e))
        
        # Prepare result message
        if error_orders:
            error_msg = "\n".join([f"- {err['name']}: {err['error']}" for err in error_orders])
            message = _(
                "Deleted %s orders successfully.\n\n"
                "Failed to delete %s orders:\n%s"
            ) % (deleted_count, len(error_orders), error_msg)
        else:
            message = _("Successfully deleted %s Rent orders with all related documents.") % deleted_count

        # Return notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Delete Rent Orders'),
                'message': message,
                'type': 'success' if not error_orders else 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
