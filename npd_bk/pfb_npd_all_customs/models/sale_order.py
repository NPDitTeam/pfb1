from itertools import chain

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    rent_count = fields.Integer(string='Rent Count', readonly=True,  compute="_get_rent")
    rent_ids = fields.Many2many("account.move", string='รับเงินประกัน', compute="_get_rent", readonly=True,
                                   copy=False,)
    rent_check = fields.Many2many("account.move", string='รับเงินประกัน', readonly=True,
                                copy=False, )

    @api.depends('rent_check')
    def _get_rent(self):
        for rec in self:
            if rec.rent_check:
                rec.rent_ids = [(4, rec.rent_ids.id)]
                rec.rent_count = len(rec.rent_check)
            else:
                rec.rent_ids = False
                rec.rent_count = 0

    def action_view_rent(self):
        invoices = self.rent_check
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', self.rent_check.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        context = {
            'default_move_type': 'out_invoice',
        }
        if len(self) == 1:
            context.update({
                'default_partner_id': self.partner_id.id,
                'default_partner_shipping_id': self.partner_shipping_id.id,
                'default_invoice_payment_term_id': self.payment_term_id.id or self.partner_id.property_payment_term_id.id or self.env['account.move'].default_get(['invoice_payment_term_id']).get('invoice_payment_term_id'),
                'default_invoice_origin': self.name,
                'default_user_id': self.user_id.id,
            })
        action['context'] = context
        return action


    def _compute_amount_insurance(self):
        for order in self:
            total = 0.0
            for line in order.order_line:
                total += (line.pfb_quantity * line.pfb_insurance_price)
                print('total', total)

            order.pfb_amount_insurance = total
            order.pfb_amount = total - order.pfb_dis_amount_insurance

    pfb_so_type = fields.Selection([
        ('sale', 'Sales'),
        ('rent', 'Rent')],
        string="Sale Type",
        index=True, default='sale', required=True)

    pfb_date_of_rent = fields.Integer(string="Day of Rent", )
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")
    pfb_amount_insurance = fields.Float('ค่าประกันสินค้า', compute='_compute_amount_insurance', digits=0)
    pfb_dis_amount_insurance = fields.Float('ส่วนลดประกันสินค้า', digits=0)
    pfb_amount = fields.Float('ค่าประกันสุทธิ', compute='_compute_amount_insurance', digits=0)

    def action_confirm(self):
        res = super().action_confirm()
        if self.picking_ids:
            if self.pfb_so_type == 'rent':
                for pk in self.picking_ids:
                    for sm in pk.move_ids_without_package:
                        sm.product_uom_qty = sm.sale_line_id.pfb_quantity
        return res

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals['pfb_so_type'] = self.pfb_so_type
        # invoice_vals['pfb_date_of_rent'] = self.pfb_date_of_rent
        invoice_vals['pfb_objective_id'] = self.pfb_objective_id.id
        invoice_vals['pfb_amount_insurance'] = self.pfb_amount_insurance
        invoice_vals['pfb_dis_amount_insurance'] = self.pfb_dis_amount_insurance
        invoice_vals['pfb_amount'] = self.pfb_amount
        return invoice_vals


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    pfb_so_rent_ok = fields.Boolean('Can be Rent', compute="_compute_so_rent_ok", store=True)
    # pfb_date_of_rent = fields.Integer(string="Day of Rent")
    pfb_date_of_rent = fields.Integer(related='order_id.pfb_date_of_rent', store=True)
    pfb_quantity = fields.Integer(string="Quantity Rent")
    pfb_insurance_price = fields.Float(string="Insurance", compute="_compute_insurance_price", store=True)
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")

    @api.onchange('pfb_quantity')
    def _onchange_pfb_quantity(self):
        self.product_uom_qty = self.pfb_date_of_rent * self.pfb_quantity

    @api.onchange('pfb_date_of_rent')
    def _onchange_pfb_date_of_rent(self):
        self.product_uom_qty = self.pfb_date_of_rent * self.pfb_quantity

    @api.depends('product_uom_qty', 'product_id')
    def _compute_insurance_price(self):

        for so_line in self:
            print('so_line', so_line.product_id)
            if so_line.product_id:
                insurance_price = self._compute_insurance_price_rule(
                    [(so_line.product_id, so_line.product_uom_qty, so_line.order_id.partner_id)], date=False,
                    uom_id=False)
                print('insurance_price', insurance_price)
                so_line.pfb_insurance_price = insurance_price
            else:
                so_line.pfb_insurance_price = 0

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        vals["pfb_quantity"] = self.pfb_quantity
        vals["pfb_insurance_price"] = self.pfb_insurance_price
        vals["pfb_so_rent_ok"] = self.pfb_so_rent_ok
        vals["pfb_objective_id"] = self.pfb_objective_id.id
        return vals

    # @api.onchange('product_id')
    # def product_id_change(self):
    #     print('self.product_id',self.product_id)
    #     print('self.product_id.product_tmpl_id',self.product_id.product_tmpl_id)
    #     res = super(SaleOrderLine, self).product_id_change()
    #     insurance_price = self._compute_insurance_price_rule([(self.product_id, self.product_uom_qty, self.order_id.partner_id)], date=False, uom_id=False)
    #     print('insurance_price',insurance_price)
    #     self.pfb_insurance_price = insurance_price
    #     return res

    def _compute_insurance_price_rule(self, products_qty_partner, date=False, uom_id=False):
        print('products_qty_partner', products_qty_partner)
        for rec in self:

            if not date:
                date = rec._context.get('date') or fields.Datetime.now()
            if not uom_id and rec._context.get('uom'):
                uom_id = rec._context['uom']
            if uom_id:
                # rebrowse with uom if given
                products = [item[0].with_context(uom=uom_id) for item in products_qty_partner]
                products_qty_partner = [(products[index], data_struct[1], data_struct[2]) for index, data_struct in
                                        enumerate(products_qty_partner)]
            else:
                products = [item[0] for item in products_qty_partner]

            if not products:
                return {}

            categ_ids = {}
            for p in products:
                categ = p.categ_id
                while categ:
                    categ_ids[categ.id] = True
                    categ = categ.parent_id
            categ_ids = list(categ_ids)

            is_product_template = products[0]._name == "product.template"
            if is_product_template:
                prod_tmpl_ids = [tmpl.id for tmpl in products]
                # all variants of all products
                prod_ids = [p.id for p in
                            list(chain.from_iterable([t.product_variant_ids for t in products]))]
            else:
                prod_ids = [product.id for product in products]
                prod_tmpl_ids = [product.product_tmpl_id.id for product in products]

            items = rec._compute_price_rule_get_items(products_qty_partner, date, uom_id, prod_tmpl_ids, prod_ids,
                                                      categ_ids)
            print('items', items)
            print('_context', rec._context)
            results = {}
            for product, qty, partner in products_qty_partner:
                results[product.id] = 0.0
                suitable_rule = False

                # Final unit price is computed according to `qty` in the `qty_uom_id` UoM.
                # An intermediary unit price may be computed according to a different UoM, in
                # which case the price_uom_id contains that UoM.
                # The final price will be converted to match `qty_uom_id`.
                qty_uom_id = rec._context.get('uom') or product.uom_id.id
                qty_in_product_uom = qty
                if qty_uom_id != product.uom_id.id:
                    try:
                        qty_in_product_uom = rec.env['uom.uom'].browse([rec._context['uom']])._compute_quantity(qty,
                                                                                                                product.uom_id)
                    except UserError:
                        # Ignored - incompatible UoM in context, use default product UoM
                        pass

                # if Public user try to access standard price from website sale, need to call price_compute.
                # TDE SURPRISE: product can actually be a template
                price = product.price_compute('list_price')[product.id]

                price_uom = rec.env['uom.uom'].browse([qty_uom_id])
                insurance_price = False
                for rule in items:
                    if rule.min_quantity and qty_in_product_uom < rule.min_quantity:
                        continue
                    if is_product_template:
                        if rule.product_tmpl_id and product.id != rule.product_tmpl_id.id:
                            continue
                        if rule.product_id and not (
                                product.product_variant_count == 1 and product.product_variant_id.id == rule.product_id.id):
                            # product rule acceptable on template if has only one variant
                            continue
                    else:
                        if rule.product_tmpl_id and product.product_tmpl_id.id != rule.product_tmpl_id.id:
                            continue
                        if rule.product_id and product.id != rule.product_id.id:
                            continue

                    if rule.categ_id:
                        cat = product.categ_id
                        while cat:
                            if cat.id == rule.categ_id.id:
                                break
                            cat = cat.parent_id
                        if not cat:
                            continue
                    print('rule', rule)
                    if rule.base == 'pricelist' and rule.base_pricelist_id:
                        price_tmp = \
                            rule.base_pricelist_id._compute_price_rule([(product, qty, partner)], date, uom_id)[
                                product.id][
                                0]  # TDE: 0 = price, 1 = rule
                        insurance_price = rule.pfb_insurance_price
                    else:
                        # if base option is public price take sale price else cost price of product
                        # price_compute returns the price in the context UoM, i.e. qty_uom_id
                        insurance_price = rule.pfb_insurance_price

                    if price is not False:
                        # pass the date through the context for further currency conversions
                        rule_with_date_context = rule.with_context(date=date)
                        insurance_price = rule.pfb_insurance_price
                        suitable_rule = rule
                    # break

                    # Final price conversion into pricelist currency
                    if suitable_rule and suitable_rule.compute_price != 'fixed' and suitable_rule.base != 'pricelist':
                        if suitable_rule.base == 'standard_price':
                            cur = product.cost_currency_id
                        else:
                            cur = product.currency_id
                        insurance_price = rule.pfb_insurance_price

                    if not suitable_rule:
                        cur = product.currency_id
                        insurance_price = rule.pfb_insurance_price

                # results[product.id] = (price, suitable_rule and suitable_rule.id or False)

        return insurance_price

    @api.depends('order_id', 'order_id.pfb_so_type')
    def _compute_so_rent_ok(self):

        for so_line in self:
            if so_line.order_id.pfb_so_type == 'sale':
                so_line.pfb_so_rent_ok = 0
            else:
                so_line.pfb_so_rent_ok = 1

    def _compute_price_rule_get_items(self, products_qty_partner, date, uom_id, prod_tmpl_ids, prod_ids, categ_ids):
        # self.ensure_one()
        # Load all rules
        self.env['product.pricelist.item'].flush(['price', 'currency_id', 'company_id', 'active'])
        print(self)
        print(self.order_id)
        print(self.order_id.name)
        print(self.order_id.pricelist_id.id)
        self.env.cr.execute(
            """
            SELECT
                item.id
            FROM
                product_pricelist_item AS item
            LEFT JOIN product_category AS categ ON item.categ_id = categ.id
            WHERE
                (item.product_tmpl_id IS NULL OR item.product_tmpl_id = any(%s))
                AND (item.product_id IS NULL OR item.product_id = any(%s))
                AND (item.categ_id IS NULL OR item.categ_id = any(%s))
                AND (item.pricelist_id = %s)
                AND (item.date_start IS NULL OR item.date_start<=%s)
                AND (item.date_end IS NULL OR item.date_end>=%s)
                AND (item.active = TRUE)
            ORDER BY
                item.applied_on, item.min_quantity desc, categ.complete_name desc, item.id desc
            """,
            (prod_tmpl_ids, prod_ids, categ_ids, self.order_id.pricelist_id.id, date, date))
        # NOTE: if you change `order by` on that query, make sure it matches
        # _order from model to avoid inconstencies and undeterministic issues.

        item_ids = [x[0] for x in self.env.cr.fetchall()]
        print('item_ids', item_ids)
        return self.env['product.pricelist.item'].browse(item_ids)

