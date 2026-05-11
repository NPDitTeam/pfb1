# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from random import randint

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

class Asset_asset_repair(models.Model):
    _inherit = 'account.asset'
    asset_ids = fields.One2many('asset.repair.order', 'account_asset_id',string='Assets')

    def open_asset_repair(self):
        self.ensure_one()
        context = dict(self.env.context)
        return {
            "name": _("Transfer"),
            "view_mode": "tree,form",
            "res_model": "asset.repair.order",
            "view_id": False,
            "type": "ir.actions.act_window",
            "context": context,
            "domain": [("id", "in", self.asset_ids.ids)],
        }

READONLY_STATES = {
    'draft': [('readonly', False)],
}

class account_asset_repair(models.Model):
    _name = 'asset.repair.order'
    _description = 'Repair Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        'Repair Reference',
        default='/',
        copy=False, required=True,
        states={'confirmed': [('readonly', True)]})
    account_asset_id = fields.Many2one(
        'account.asset', string='Product to Repair',
        readonly=True, required=True,
        states=READONLY_STATES, check_company=True)
    code = fields.Char('Reference', related='account_asset_id.code',states=READONLY_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('under_repair', 'Under Repair'),
        ('ready', 'Ready to Repair'),
        ('done', 'Repaired'),
        ('cancel', 'Cancelled')], string='Status',
        copy=False, default='draft', readonly=True, tracking=True,
        help="* The \'Draft\' status is used when a user is encoding a new and unconfirmed repair order.\n"
             "* The \'Confirmed\' status is used when a user confirms the repair order.\n"
             "* The \'Ready to Repair\' status is used to start to repairing, user can start repairing only after repair order is confirmed.\n"
             "* The \'To be Invoiced\' status is used to generate the invoice before or after repairing done.\n"
             "* The \'Done\' status is set when repairing is completed.\n"
             "* The \'Cancelled\' status is used when user cancel repair order.")
    guarantee_limit = fields.Date('Warranty Expiration', states={'confirmed': [('readonly', True)]})
    date_of_completion = fields.Date('Date of completion', states={'confirmed': [('readonly', True)]})
    approved_date = fields.Date('Approved Date', help="Date the asset was finished. ", readonly=True)
    pricelist_id = fields.Many2one(
        'product.pricelist', 'Pricelist',
        default=lambda self: self.env['product.pricelist'].search([('company_id', 'in', [self.env.company.id, False])], limit=1).id,
        help='Pricelist of the selected partner.', check_company=True)
    currency_id = fields.Many2one(related='pricelist_id.currency_id')
    internal_notes = fields.Text('Internal Notes',states={'draft': [('readonly', False)]})
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user, check_company=True)
    user_id_repair = fields.Many2one('res.users', string="Repair person",check_company=True,states={'draft': [('readonly', False)]})
    user_id_approve = fields.Many2one('res.users', string="Approve person", check_company=True,states={'draft': [('readonly', False)]})
    operations = fields.One2many(
        'asset.repair.line', 'repair_id', 'Parts',
        copy=True, readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one(
        'res.company', 'Company',
        readonly=True, required=True, index=True,
        default=lambda self: self.env.company)
    remark = fields.Char('Symptoms / Causes',states={'draft': [('readonly', False)]})
    # tag_ids = fields.Many2many(comodel_name='asset.repair.tags', string="Symptoms / Causes")
    amount_untaxed = fields.Float('Untaxed Amount', compute='_amount_untaxed', store=True)
    amount_tax = fields.Float('Taxes', compute='_amount_tax', store=True)
    amount_total = fields.Float('Total', compute='_amount_total', store=True)
    reference = fields.Char('Reference Number', states=READONLY_STATES)
    api_channel = fields.Char('Api Channel', states=READONLY_STATES)

    _sql_constraints = [
        ('name', 'unique (name)', 'The name of the Repair Order must be unique!'),
    ]

    @api.depends('partner_id')
    def _compute_default_address_id(self):
        for order in self:
            if order.partner_id:
                order.default_address_id = order.partner_id.address_get(['contact'])['contact']

    @api.depends('operations.price_subtotal', 'pricelist_id.currency_id')
    def _amount_untaxed(self):
        for order in self:
            total = sum(operation.price_subtotal for operation in order.operations)
            # total += sum(fee.price_subtotal for fee in order.fees_lines)
            order.amount_untaxed = order.pricelist_id.currency_id.round(total)

    @api.depends('operations.price_unit', 'operations.product_uom_qty', 'operations.product_id', 'pricelist_id.currency_id')
    def _amount_tax(self):
        for order in self:
            val = 0.0
            for operation in order.operations:
                if operation.tax_id:
                    tax_calculate = operation.tax_id.compute_all(operation.price_unit, order.pricelist_id.currency_id,
                                                                 operation.product_uom_qty, operation.product_id,
                                                                 None)
                    for c in tax_calculate['taxes']:
                        val += c['amount']
            order.amount_tax = val

    @api.depends('amount_untaxed', 'amount_tax')
    def _amount_total(self):
        for order in self:
            order.amount_total = order.pricelist_id.currency_id.round(order.amount_untaxed + order.amount_tax)

    @api.model
    def create(self, vals):
        # To avoid consuming a sequence number when clicking on 'Create', we preprend it if the
        # the name starts with '/'.
        vals['name'] = vals.get('name') or '/'
        if vals['name'].startswith('/'):
            vals['name'] = (self.env['ir.sequence'].next_by_code('asset.repair.order') or '/') + vals['name']
            vals['name'] = vals['name'][:-1] if vals['name'].endswith('/') and vals['name'] != '/' else vals['name']
        return super(account_asset_repair, self).create(vals)

    def button_dummy(self):
        # TDE FIXME: this button is very interesting
        return True

    def action_repair_cancel_draft(self):
        if self.filtered(lambda repair: repair.state != 'cancel'):
            raise UserError(_("Repair must be canceled in order to reset it to draft."))
        self.mapped('operations').write({'state': 'draft'})
        return self.write({'state': 'draft'})

    def action_validate(self):
        return self.write({"state": "confirmed"})

    def action_repair_cancel(self):
        return self.write({'state': 'cancel'})

    def print_repair_order(self):
        return self.env.ref('repair.action_report_repair_order').report_action(self)

    def action_repair_ready(self):
        self.mapped('operations').write({'state': 'confirmed'})
        return self.write({'state': 'ready'})

    def action_repair_start(self):
        """ Writes repair order state to 'Under Repair'
        @return: True
        """
        if self.filtered(lambda repair: repair.state not in ['confirmed', 'ready']):
            raise UserError(_("Repair must be confirmed before starting reparation."))
        self.mapped('operations').write({'state': 'confirmed'})
        return self.write({'state': 'under_repair','approved_date': fields.Date.today(),'user_id_approve':self.env.context['uid']})

    def action_repair_end(self):
        """ Writes repair order state to 'To be invoiced' if invoice method is
        After repair else state is set to 'Ready'.
        @return: True
        """
        if self.filtered(lambda repair: repair.state != 'under_repair'):
            raise UserError(_("Repair must be under repair in order to end reparation."))

        return self.write({'state': 'done'})

    # def action_repair_done(self):
    #     """ Creates stock move for operation and stock move for final product of repair order.
    #     @return: Move ids of final products
    #
    #     """
    #     return res

class AssetRepairLine(models.Model):
    _name = 'asset.repair.line'
    _description = 'Repair Line (parts)'

    name = fields.Text('Description', required=True)
    repair_id = fields.Many2one(
        'asset.repair.order', 'Repair Order Reference', required=True,
        index=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        related='repair_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(
        related='repair_id.currency_id')
    product_id = fields.Many2one(
        'product.product', 'Product', required=True, check_company=True,
        domain="[('type', 'in', ['product', 'consu']), '|', ('company_id', '=', company_id), ('company_id', '=', False)]")
    # invoiced = fields.Boolean('Invoiced', copy=False, readonly=True)
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price')
    price_subtotal = fields.Float('Subtotal', compute='_compute_price_subtotal', store=True, digits=0)
    tax_id = fields.Many2many(
        'account.tax', 'asset_repair_operation_line_tax', 'asset_repair_operation_line_id', 'tax_id', 'Taxes',
        domain="[('type_tax_use','=','sale'), ('company_id', '=', company_id)]", check_company=True)
    product_uom_qty = fields.Float(
        'Quantity', default=1.0,
        digits='Product Unit of Measure', required=True)
    product_uom = fields.Many2one(
        'uom.uom', 'Product Unit of Measure',
        required=True, domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lot/Serial',
        domain="[('product_id','=', product_id), ('company_id', '=', company_id)]", check_company=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], 'Status', default='draft',
        copy=False, readonly=True, required=True,
        help='The status of a repair line is set automatically to the one of the linked repair order.')

    @api.constrains('lot_id', 'product_id')
    def constrain_lot_id(self):
        for line in self.filtered(lambda x: x.product_id.tracking != 'none' and not x.lot_id):
            raise ValidationError(_("Serial number is required for operation line with product '%s'") % (line.product_id.name))
    #
    @api.depends('price_unit', 'repair_id', 'product_uom_qty', 'product_id')
    def _compute_price_subtotal(self):
        for line in self:
            taxes = line.tax_id.compute_all(line.price_unit, line.repair_id.pricelist_id.currency_id, line.product_uom_qty, line.product_id, None)
            line.price_subtotal = taxes['total_excluded']
