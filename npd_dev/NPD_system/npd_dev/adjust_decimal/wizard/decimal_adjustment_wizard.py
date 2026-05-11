from odoo import models, fields, api
from odoo.exceptions import UserError


class DecimalAdjustmentWizard(models.TransientModel):
    _name = 'decimal.adjustment.wizard'
    _description = 'Wizard for Adjusting Grand Total Decimal'

    move_id = fields.Many2one('account.move', string='เอกสาร', readonly=True)
    current_total = fields.Float(
        string='รวมปัจจุบัน', readonly=True, digits=(16, 2)
    )
    integer_part = fields.Integer(string='จำนวนเต็ม', readonly=True)
    new_decimal = fields.Integer(string='ทศนิยมใหม่ (0-99)')
    target_total = fields.Float(
        string='รวมเป้าหมาย', readonly=True, digits=(16, 2)
    )
    difference = fields.Float(
        string='ผลต่าง', readonly=True, digits=(16, 2)
    )

    adjust_line_id = fields.Many2one(
        'account.move.line', string='รายการที่ปรับ', readonly=True,
    )
    adjust_line_name = fields.Char(
        string='สินค้าที่ปรับ', readonly=True,
    )
    line_current_price = fields.Float(
        string='ราคาปัจจุบัน', readonly=True, digits=(16, 5)
    )
    line_new_price = fields.Float(
        string='ราคาใหม่', readonly=True, digits=(16, 5)
    )

    line_ids = fields.One2many(
        'decimal.adjustment.wizard.line', 'wizard_id',
        string='รายการทั้งหมด',
    )

    # ----------------------------------------------------------------
    # Default
    # ----------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super(DecimalAdjustmentWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            move = self.env['account.move'].browse(active_id)
            res['move_id'] = move.id
            current_total = round(move.amount_total, 2)
            res['current_total'] = current_total
            integer_part = int(current_total)
            res['integer_part'] = integer_part
            res['new_decimal'] = int(
                round((current_total - integer_part) * 100)
            )
            res['target_total'] = current_total
            res['difference'] = 0.0

            invoice_lines = move.invoice_line_ids
            if invoice_lines:
                last_line = invoice_lines[-1]
                res['adjust_line_id'] = last_line.id
                res['adjust_line_name'] = (
                    last_line.product_id.display_name
                    or last_line.name or ''
                )
                res['line_current_price'] = last_line.price_unit
                res['line_new_price'] = last_line.price_unit

            lines = []
            for line in invoice_lines:
                lines.append((0, 0, {
                    'move_line_id': line.id,
                    'product_name': (
                        line.product_id.display_name or line.name or ''
                    ),
                    'quantity': line.quantity,
                    'current_price': line.price_unit,
                    'current_subtotal': line.price_subtotal,
                }))
            res['line_ids'] = lines
        return res

    # ----------------------------------------------------------------
    # Onchange
    # ----------------------------------------------------------------
    @api.onchange('new_decimal')
    def _onchange_new_decimal(self):
        target = self.integer_part + (self.new_decimal / 100.0)
        self.target_total = target
        diff = round(target - self.current_total, 2)
        self.difference = diff

        line = self.adjust_line_id
        if line and line.quantity and abs(diff) > 0.001:
            self.line_new_price = self._calculate_new_price(line, target)
        else:
            self.line_new_price = self.line_current_price

    # ----------------------------------------------------------------
    # Core calculation
    # ----------------------------------------------------------------
    @staticmethod
    def _get_line_tax_include_pct(line):
        """Get the price-include tax percentage for a line (e.g. 7 for VAT 7%)"""
        for tax in line.tax_ids:
            if tax.price_include and tax.amount > 0:
                return tax.amount
        return 0.0

    @staticmethod
    def _compute_stwd(price_unit, quantity, tax_include_pct):
        """
        Compute price_subtotal_without_discount using the SAME formula
        as bi_sale_purchase_discount_with_tax:
            stwd = (price * qty) * (100 / (100 + tax%))
        """
        return (price_unit * quantity) * (100.0 / (100.0 + tax_include_pct))

    def _calculate_new_price(self, line, target_total):
        """
        Calculate new price by computing other_stwd from ALL other lines'
        actual price_unit values (not from stored fields that may be stale).
        """
        move = line.move_id
        qty = line.quantity
        if not qty:
            return line.price_unit

        tax_pct = self._get_line_tax_include_pct(line)

        # Compute sum of stwd for all OTHER invoice lines from their prices
        other_stwd = 0.0
        for other_line in move.invoice_line_ids:
            if other_line.id == line.id:
                continue
            other_tax_pct = self._get_line_tax_include_pct(other_line)
            other_stwd += self._compute_stwd(
                other_line.price_unit,
                other_line.quantity,
                other_tax_pct,
            )

        # Target stwd sum:
        # amount_total = stwd_sum + amount_tax - discount
        # stwd_sum = target_total - amount_tax + discount
        amount_tax = move.amount_tax
        discount = getattr(move, 'discount_amt_line', 0.0) or 0.0
        target_stwd_sum = target_total - amount_tax + discount

        # New stwd for this line
        new_stwd = target_stwd_sum - other_stwd

        # Reverse: price = stwd * (100 + tax%) / 100 / qty
        new_price = new_stwd * (100.0 + tax_pct) / 100.0 / qty
        return new_price

    # ----------------------------------------------------------------
    # Actions
    # ----------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        if self.move_id.state != 'draft':
            raise UserError(
                'สามารถแก้ไขได้เฉพาะสถานะฉบับร่างเท่านั้น'
            )

        target = self.integer_part + (self.new_decimal / 100.0)
        diff = round(target - self.current_total, 2)

        if abs(diff) < 0.001:
            return {'type': 'ir.actions.act_window_close'}

        line = self.adjust_line_id
        if not line:
            raise UserError('ไม่พบรายการสำหรับปรับราคา')
        if not line.quantity:
            raise UserError('จำนวนสินค้าเป็น 0')

        new_price = self._calculate_new_price(line, target)

        # Write price_unit — Odoo _compute_amount will:
        # 1. Recompute stwd for this line
        # 2. Recompute amount_price_subtotal_without_discount
        # 3. Recompute amount_total = stwd_sum + tax - discount
        line.with_context(check_move_validity=False).write({
            'price_unit': new_price,
        })

        # Recompute tax lines and receivable/payable
        self.move_id.with_context(
            check_move_validity=False
        )._recompute_dynamic_lines(recompute_all_taxes=True)

        return {'type': 'ir.actions.act_window_close'}

    # ----------------------------------------------------------------
    # Constraints
    # ----------------------------------------------------------------
    @api.constrains('new_decimal')
    def _check_new_decimal(self):
        for wiz in self:
            if wiz.new_decimal < 0 or wiz.new_decimal > 99:
                raise UserError('ทศนิยมต้องอยู่ระหว่าง 0-99')


class DecimalAdjustmentWizardLine(models.TransientModel):
    _name = 'decimal.adjustment.wizard.line'
    _description = 'Decimal Adjustment Wizard Line (Reference)'

    wizard_id = fields.Many2one(
        'decimal.adjustment.wizard', string='Wizard', ondelete='cascade'
    )
    move_line_id = fields.Many2one('account.move.line', string='Invoice Line')
    product_name = fields.Char(string='สินค้า', readonly=True)
    quantity = fields.Float(string='จำนวน', readonly=True)
    current_price = fields.Float(
        string='ราคา', readonly=True, digits=(16, 5)
    )
    current_subtotal = fields.Float(
        string='รวม', readonly=True, digits=(16, 2)
    )
