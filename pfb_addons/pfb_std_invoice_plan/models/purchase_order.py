from odoo import models, fields, api, _
from odoo.tools.float_utils import float_compare, float_round, float_repr
from odoo.exceptions import ValidationError, UserError
from math import log10, floor


class PurchaseOrderInvoiceInherit(models.Model):
    _inherit = 'purchase.order'

    percent_all = fields.Float(string='Percent', readonly=True, compute='_percent_all', digits=(12, 2))
    amount_all = fields.Float(string='Amount', readonly=True, compute='_percent_all', digits=(12, 2))
    hide_button = fields.Boolean(
        compute='_invoice_plan_count',
    )
    hide_wa_button = fields.Boolean(
        compute='_wa_count',
    )

    def round_to_1(self, x):
        return round(x, -int(floor(log10(abs(x)))))

    def _wa_count(self):
        if len(self.invoice_plan_ids) != 0:
            wa_obj = self.env['work.acceptance.line'].search([
                ('wa_id.purchase_id', '=', self.id),
                ('wa_id.state', '=', 'accept'),
            ])
            sum_amount = 0
            for wa in wa_obj:
                sum_amount += wa.price_subtotal

            price_total = self.amount_untaxed - sum_amount
            print(price_total, 'case1')
            if price_total == 0:
                self.hide_wa_button = True
            else:
                self.hide_wa_button = False
        else:
            self.hide_wa_button = False

    def _invoice_plan_count(self):
        if len(self.invoice_plan_ids) == len(self.invoice_plan_ids.filtered(lambda x: x.invoiced == True)):
            self.hide_button = True
        else:
            self.hide_button = False
            for line_order in self.order_line:
                if line_order.qty_to_invoice < 0:
                    line_order.qty_to_invoice = 0

    @api.depends('invoice_plan_ids.percent')
    def _percent_all(self):
        for rec in self:
            percent_total = 0.00
            amount_total = 0.00
            # amount_total2 = float_round(sum(line.amount_invoice_plan for line in rec.invoice_plan_ids), 1)
            for line in rec.invoice_plan_ids:
                percent_total += line.percent
                amount_total += line.amount_invoice_plan
            rec.update({
                'percent_all': percent_total,
                'amount_all': amount_total,
            })

    # Create Invoice Plan
    def create_invoice_plan(self, num_installment, installment_date,
                            interval, interval_type):
        self.ensure_one()
        self.invoice_plan_ids.unlink()
        invoice_plans = []
        Decimal = self.env['decimal.precision']
        prec = Decimal.precision_get('Product Unit of Measure')
        percent = float_round(1.0 / num_installment * 100, prec)
        percent_last = 100 - (percent * (num_installment - 1))
        sum_amount = self.amount_total
        amount_plan = sum_amount / num_installment
        # print(amount_plan)
        for i in range(num_installment):
            this_installment = i + 1
            if num_installment == this_installment:
                percent = percent_last
                amount_plan = amount_plan
                # print(amount_plan, 2)
            vals = {'installment': this_installment,
                    'plan_date': installment_date,
                    'invoice_type': 'installment',
                    'percent': percent,
                    'amount_invoice_plan': amount_plan, }
            invoice_plans.append((0, 0, vals))
            installment_date = self._next_date(installment_date,
                                               interval, interval_type)
        self.write({'invoice_plan_ids': invoice_plans})
        return True

    # # Write
    def write(self, vals):
        percent_total = 0
        amount_total = 0
        print(vals)
        if 'invoice_plan_ids' in vals:
            for plan_ids in vals['invoice_plan_ids']:
                # for plan_id in plan_ids:
                if plan_ids[2]:
                    if 'percent' in plan_ids[2]:
                        percent_total += plan_ids[2]['percent']

                    if 'amount_invoice_plan' in plan_ids[2]:
                        amount_total += plan_ids[2]['amount_invoice_plan']
                    else:
                        percent_total += self.env['purchase.invoice.plan'].search([('id', '=', plan_ids[1])]).percent
                        amount_total += self.env['purchase.invoice.plan'].search(
                            [('id', '=', plan_ids[1])]).amount_invoice_plan
                else:
                    percent_total += self.env['purchase.invoice.plan'].search([('id', '=', plan_ids[1])]).percent
                    amount_total += self.env['purchase.invoice.plan'].search(
                        [('id', '=', plan_ids[1])]).amount_invoice_plan

            # if self.round_to_1(percent_total) != 100 and percent_total > 0:
            #     # print(self.round_to_1(percent_total), 3)
            #     raise ValidationError(_("The percentage number must be 100."))
            # if len(self.invoice_plan_ids) != 0:
            #     if amount_total != self.amount_total and percent_total > 0:
            #         raise ValidationError(_("ยอดเงินไม่ถูกต้อง"))
        res = super(PurchaseOrderInvoiceInherit, self).write(vals)
        return res

    # # WA
    def action_view_wa(self):
        if len(self.invoice_plan_ids) == 0:
            self.ensure_one()
            act = self.env.ref('purchase_work_acceptance.action_work_acceptance')
            result = act.read()[0]
            create_wa = self.env.context.get('create_wa', False)
            result['context'] = {
                'default_purchase_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_company_id': self.company_id.id,
                'default_currency_id': self.currency_id.id,
                'default_date_due': self.date_planned,
                'default_wa_line_ids': [(0, 0, {
                    'purchase_line_id': line.id,
                    'name': line.name,
                    'product_uom': line.product_uom.id,
                    'product_id': line.product_id.id,
                    'price_unit': line.price_unit,
                    'product_qty': line.product_qty,
                }) for line in self.order_line if line.price_unit != 0],
            }
            if len(self.wa_ids) > 1 and not create_wa:
                result['domain'] = "[('id', 'in', " + str(self.wa_ids.ids) + ")]"
            else:
                res = self.env.ref(
                    'purchase_work_acceptance.view_work_acceptance_form', False)
                result['views'] = [(res and res.id or False, 'form')]
                if not create_wa:
                    result['res_id'] = self.wa_ids.id or False
            return result
        if len(self.invoice_plan_ids) != 0:
            wa_obj = self.env['work.acceptance.line'].search([
                ('wa_id.purchase_id', '=', self.id),
                ('wa_id.state', '=', 'accept'),
            ])
            sum_amount = 0
            for wa in wa_obj:
                sum_amount += wa.price_subtotal

            price_total = self.amount_untaxed - sum_amount
            print(price_total, 4)

            self.ensure_one()
            act = self.env.ref('purchase_work_acceptance.action_work_acceptance')
            result = act.read()[0]
            sum_total_po = 0.00
            sum_qty = 0
            sum_price_unit = []
            installment_pl = 0
            sum_total_po = self.amount_total
            unit_po = []
            po_i = 0
            count_po = 0
            po_wa = 0
            tax = []
            for line_po in self.order_line:
                sum_qty += line_po.product_qty
                unit_po.append(line_po.price_unit)
                count_po += 1
                if line_po.taxes_id:
                    if line_po.taxes_id.price_include:
                        tax.append('0')
                    else:
                        tax.append('1')

            for line_invoice_plan in self.invoice_plan_ids:
                if line_invoice_plan.to_invoice:
                    installment_pl = line_invoice_plan.installment
                    for cc in range(count_po):
                        if tax:
                            if tax[po_i] == '1':
                                sum_price_unit.append(
                                    line_invoice_plan.amount_invoice_plan *
                                    (unit_po[po_i] + (unit_po[po_i] * 0.07)) / sum_total_po)
                            else:
                                sum_price_unit.append(
                                    (line_invoice_plan.amount_invoice_plan * unit_po[po_i]) / sum_total_po)
                        else:
                            sum_price_unit.append(
                                (line_invoice_plan.amount_invoice_plan * unit_po[po_i]) / sum_total_po)
                        po_i += 1
            for cc in self.order_line:
                print(sum_price_unit, 'case01')
                if sum_price_unit:
                    cc.write({'amount_wa': sum_price_unit[po_wa]})
                po_wa += 1

                # sum_price_unit = line_invoice_plan.amount_invoice_plan / sum_qty
            create_wa = self.env.context.get('create_wa', False)
            result['context'] = {
                'default_purchase_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_company_id': self.company_id.id,
                'default_currency_id': self.currency_id.id,
                'default_date_due': self.date_planned,
                'default_instalment_wa': installment_pl,
                'default_wa_line_ids': [(0, 0, {
                    'purchase_line_id': line.id,
                    'name': line.name,
                    'product_uom': line.product_uom.id,
                    'product_id': line.product_id.id,
                    'price_unit': line.amount_wa,
                    'product_qty': line.product_qty,
                    'price_subtotal': line.amount_wa * line.product_qty,
                }) for line in self.order_line],
            }
            if len(self.wa_ids) > 1 and not create_wa:
                result['domain'] = "[('id', 'in', " + str(self.wa_ids.ids) + ")]"
            else:
                res = self.env.ref(
                    'purchase_work_acceptance.view_work_acceptance_form', False)
                result['views'] = [(res and res.id or False, 'form')]
                if not create_wa:
                    result['res_id'] = self.wa_ids.id or False
            return result


class PurchaseOrderLineInherit(models.Model):
    _inherit = 'purchase.order.line'

    amount_wa = fields.Float(string='Amount Wa', readonly=True, digits=(12, 2))

    def _prepare_account_move_line(self, move=False):
        print('_prepare_account_move_line', 'case01')
        self.ensure_one()
        price = 0.00
        aml_currency = move and move.currency_id or self.currency_id
        date = move and move.date or fields.Date.today()
        if self.order_id.invoice_plan_ids:
            for inv_plan in self.order_id.invoice_plan_ids:
                if inv_plan.to_invoice:
                    if self.taxes_id:
                        if not self.taxes_id.price_include:
                            percent = 7/107
                            price = inv_plan.amount_invoice_plan - (inv_plan.amount_invoice_plan * percent)
                        else:
                            price = inv_plan.amount_invoice_plan

                    else:
                        price = inv_plan.amount_invoice_plan
                    qty_to_invoice = self.product_qty
        else:
            price = self.currency_id._convert(self.price_unit, aml_currency, self.company_id, date, round=False)
            qty_to_invoice = self.qty_to_invoice
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': '%s: %s' % (self.order_id.name, self.name),
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': qty_to_invoice,
            'price_unit': price,
            'discount': self.discount,
            'tax_ids': [(6, 0, self.taxes_id.ids)],
            'analytic_account_id': self.account_analytic_id.id,
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'purchase_line_id': self.id,
        }
        if not move:
            return res

        if self.currency_id == move.company_id.currency_id:
            currency = False
        else:
            currency = move.currency_id

        res.update({
            'move_id': move.id,
            'currency_id': currency and currency.id or False,
            'date_maturity': move.invoice_date_due,
            'partner_id': move.partner_id.id,
        })
        return res
