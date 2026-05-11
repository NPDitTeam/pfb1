# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models

class account_asset_repair_report(models.Model):
    _name = 'asset.repair.order.report'
    _auto = False
    _rec_name = 'create_date'
    _order = 'create_date desc'

    create_date = fields.Date('Create Date', readonly=True)
    name = fields.Char('Repair Reference', readonly=True)
    account_asset_id = fields.Many2one('account.asset', string='Product to Repair', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('under_repair', 'Under Repair'),
        ('ready', 'Ready to Repair'),
        ('done', 'Repaired'),
        ('cancel', 'Cancelled')], string='Status', readonly=True )
    guarantee_limit = fields.Date('Warranty Expiration',  readonly=True)
    date_of_completion = fields.Date('Date of completion', readonly=True)
    approved_date = fields.Date('Approved Date', help="Date the asset was finished.", readonly=True)
    pricelist_id = fields.Many2one('product.pricelist', 'Pricelist', readonly=True, invisible=True)
    # currency_id = fields.Many2one(related='pricelist_id.currency_id', readonly=True, invisible=True)
    internal_notes = fields.Text('Internal Notes',readonly=True)
    user_id = fields.Many2one('res.users', string="Responsible", readonly=True )
    user_id_repair = fields.Many2one('res.users', string="Repair person", check_company=True, readonly=True)
    user_id_approve = fields.Many2one('res.users', string="Approve person", check_company=True, readonly=True)
    # operations = fields.One2many('asset.repair.line', 'repair_id', 'Parts',readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True, invisible=True)
    remark = fields.Char('Symptoms / Causes', readonly=True)
    # amount_untaxed = fields.Float('Untaxed Amount', compute='_amount_untaxed', readonly=True)
    # amount_tax = fields.Float('Taxes', readonly=True)
    # amount_total = fields.Float('Total',readonly=True)
    product_id = fields.Many2one(
        'product.product', 'Product', required=True, check_company=True,)
    # invoiced = fields.Boolean('Invoiced', readonly=True)
    price_unit = fields.Float('Unit Price', digits='Product Price', readonly=True)
    price_subtotal = fields.Float('Subtotal',digits=0,readonly=True)
    product_uom_qty = fields.Float('Quantity', default=1.0, digits='Product Unit of Measure', readonly=True)
    product_uom = fields.Many2one('uom.uom', 'Product Unit of Measure', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
              CREATE or REPLACE view %s as (
                SELECT 
                    l.id
                    ,o.create_date
                    ,o.name 
                    ,o.account_asset_id
                    ,o.state
                    ,o.guarantee_limit
                    ,o.date_of_completion
                    ,o.approved_date
                    ,o.pricelist_id
                    --,o.currency_id
                    ,o.internal_notes
                    ,o.user_id
                    ,o.user_id_repair
                    ,o.user_id_approve
                    ,o.remark
                    ,l.product_id
                    ,l.price_unit
                    ,l.price_subtotal
                    ,l.product_uom_qty
                    ,l.product_uom
                FROM asset_repair_line l 
                LEFT JOIN asset_repair_order o ON o.id = l.repair_id
              );
          """ % self._table)

    #
    # def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
    #     with_ = ("WITH %s" % with_clause) if with_clause else ""
    #     select_ = ''
    #     from_ = ''
    #     groupby_ = ''
    #
    #     return '%s (SELECT %s FROM %s GROUP BY %s)' % (with_, select_, from_, groupby_)
    #
    # def init(self):
    #     # self._table = sale_report
    #     tools.drop_view_if_exists(self.env.cr, self._table)
    #     self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
