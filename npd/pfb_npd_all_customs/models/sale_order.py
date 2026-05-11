from itertools import chain

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang

# from Demos.FileSecurityTest import permissions


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    rent_count = fields.Integer(string='Rent Count', readonly=True,  compute="_get_rent")
    rent_ids = fields.Many2many("account.move", string='รับเงินประกัน', compute="_get_rent", readonly=True,
                                   copy=False,)
    rent_check = fields.Many2many("account.move", string='รับเงินประกัน', readonly=True,
                                copy=False, )
    date_order_x = fields.Date(string="วันที่สั่งซื้อ", store=True)

    npd_so_type = fields.Selection([
        ('sale', 'Sales'),
        ('rent', 'Rent')],
        string="Sale Type",
        index=True, default='sale', required=True)

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


    # def _compute_amount_insurance(self):
    #     for order in self:
    #         total = 0.0
    #         for line in order.order_line:
    #             total += (line.pfb_quantity * line.pfb_insurance_price)
    #             print('total', total)
    #
    #         order.pfb_amount_insurance = total
    #         order.pfb_amount = total - order.pfb_dis_amount_insurance
    #
    #     for record in self:
    #         # คำนวณค่าประกันต่ำสุด (15% ของ pfb_amount_insurance)
    #         record.pfb_insurance_min = record.pfb_amount_insurance * 0.15 if record.pfb_amount_insurance else 0.0
    #         # คำนวณค่าประกันสุทธิ
    #         record.pfb_amount = max(0, record.pfb_amount_insurance - record.pfb_dis_amount_insurance)

    pfb_so_type = fields.Selection([
        ('sale', 'Sales'),
        ('rent', 'Rent')],
        string="Sale Type",
        index=True, default='sale', required=True)

    pfb_date_of_rent = fields.Integer(string="Day of Rent", )
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")
    pfb_amount_insurance = fields.Float('ค่าประกันสินค้า', compute='_compute_amount_insurance', digits=0)
    pfb_dis_amount_insurance = fields.Float('ส่วนลดประกันสินค้า', digits=0)
    pfb_amount = fields.Float('ค่าประกันสุทธิ', compute='_compute_amount_insurance', digits=0, store=True)

    pfb_insurance_min = fields.Float('ค่าประกันต่ำสุดไม่เกิน',  store=True)
    pfb_required_insurance_premium = fields.Float('กรอกจำนวนค่าประกันที่ต้องการ', store=True)

    pfb_amount_insurance_c = fields.Float('ค่าประกันสินค้า สำนา',0, store=True)
    pfb_amount_c = fields.Float('ค่าประกันสุทธิ สำนา', 0, store=True)

    # pfb_insurance_min = fields.Float('ค่าประกันต่ำสุดไม่เกิน', compute='_compute_insurance_min', store=True)

    approver_id = fields.Many2one(
        'res.users', string="Approver", readonly=True,
        help="User who approved this order."
    )

    note_approver = fields.Text(string='Approval Note',  store=True)  # Add this line


    @api.onchange('pfb_required_insurance_premium')
    def _onchange_required_insurance_premium(self):
        """ เมื่อผู้ใช้กรอกค่าประกันที่ต้องการ ให้คำนวณส่วนลดใหม่ """
        for record in self:
            if record.state != 'draft' or record.quotation_state == 'draft':
                if not record.deposit_ref:

                    record.pfb_dis_amount_insurance = record.pfb_amount_insurance - record.pfb_required_insurance_premium
            else:
                record.pfb_amount_insurance = record.pfb_amount_insurance_c or 0.0
                record.pfb_amount = record.pfb_amount_c or 0.0

    def action_waiting_to_approve(self):
        """เปิด Popup สำหรับเลือก Approver"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Approver'),
            'res_model': 'sale.order.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    def action_update_insurance_amount(self):
        for record in self:
            if not record.deposit_ref:
                raise UserError("ไม่มีค่าในฟิลด์ deposit_ref")

            # แปลง deposit_ref เป็น list
            so_list = [x.strip() for x in record.deposit_ref.split(",") if x.strip()]
            if not so_list:
                raise UserError("ไม่พบเลขที่ SO ที่ถูกต้องใน deposit_ref")

            # ดึง SO แรกเป็นต้นทาง
            source_so_name = so_list[0]
            source_so = self.env['sale.order'].search([('name', '=', source_so_name)], limit=1)
            if not source_so:
                raise UserError(f"ไม่พบ SO ต้นทาง: {source_so_name}")

            insurance_value = source_so.pfb_amount_insurance
            amount_value = source_so.pfb_amount

            # print("📦 ค่าอ้างอิงต้นฉบับ:")
            # print("pfb_amount_insurance =", insurance_value)
            # print("pfb_amount =", amount_value)

            updated_count = 0

            for so_name in so_list:
                target_so = self.env['sale.order'].search([('name', '=', so_name)], limit=1)
                if target_so:
                    # print(f"\n➡️ SO: {so_name}")
                    # print("⏳ ก่อนอัปเดต:")
                    # print("  insurance_c =", target_so.pfb_amount_insurance_c)
                    # print("  amount_c =", target_so.pfb_amount_c)

                    # target_so.write({
                    #     # 'pfb_amount_insurance': insurance_value,
                    #     # 'pfb_amount': amount_value,
                    #     'pfb_amount_insurance_c': insurance_value,
                    #     'pfb_amount_c': amount_value
                    # })
                    record.pfb_amount_insurance = insurance_value
                    record.pfb_amount = amount_value
                    record.pfb_amount_insurance_c = insurance_value
                    record.pfb_amount_c = amount_value
                    # อ่านใหม่หลังเขียน
                    target_so.invalidate_cache()

                    # print("✅ หลังอัปเดต:")
                    # print("  insurance_c =", target_so.pfb_amount_insurance_c)
                    # print("  amount_c =", target_so.pfb_amount_c)

                    updated_count += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'สำเร็จ 🎉',
                    'message': f'อัปเดตแล้วเงินประกันแล้ว',
                    'type': 'success',
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'reload',
                    },
                }
            }

    @api.depends('order_line.pfb_quantity', 'order_line.pfb_insurance_price', 'pfb_dis_amount_insurance','pfb_required_insurance_premium')
    def _compute_amount_insurance(self):
        for order in self:
            if order.state != 'draft' or order.quotation_state == 'draft':
                if order.deposit_ref:
                    # ✅ ถ้ามีค่า deposit_ref แล้ว ไม่ต้องคำนวณใหม่ → ดึงค่าที่เคยมีอยู่

                    order.pfb_amount_insurance = order.pfb_amount_insurance_c or 0.0
                    order.pfb_amount = order.pfb_amount_c or 0.0



                else:
                    total = 0.0

                    if "order_line" in order._fields:
                        for line in order.order_line:
                            if "pfb_quantity" in line._fields and "pfb_insurance_price" in line._fields:
                                total += (line.pfb_quantity * line.pfb_insurance_price)

                    if "pfb_amount_insurance" in order._fields:
                        order.pfb_amount_insurance = total
                        order.pfb_amount_insurance_c = order.pfb_amount_insurance

                    if "pfb_dis_amount_insurance" in order._fields and "pfb_amount" in order._fields:
                        order.pfb_amount = max(0, total - order.pfb_dis_amount_insurance)
                        order.pfb_amount_c = order.pfb_amount

                    if "pfb_insurance_min" in order._fields and "pfb_amount_insurance" in order._fields:
                        order.pfb_insurance_min = order.pfb_amount_insurance * 0.15 if order.pfb_amount_insurance else 0.0

            else:
                order.pfb_amount_insurance = order.pfb_amount_insurance_c or 0.0
                order.pfb_amount = order.pfb_amount_c or 0.0

    @api.onchange('pfb_dis_amount_insurance')
    def _check_insurance_minimum(self):
        for record in self:
            if "pfb_amount_insurance" in record._fields and "pfb_insurance_min" in record._fields and "pfb_amount" in record._fields:
                if record.pfb_amount >= 0 and record.pfb_amount < record.pfb_insurance_min:
                    return {
                        'warning': {
                            'title': _("แจ้งเตือน!"),
                            'message': _(
                                "ค่าประกันต่ำกว่ามาตรฐานที่กำหนด (%.2f บาท). โปรดส่งคำขออนุมัติจากผู้จัดการ." % record.pfb_insurance_min),
                        }
                    }



    def action_confirm(self):
        res = super().action_confirm()
        if self.picking_ids:
            if self.pfb_so_type == 'rent':
                for pk in self.picking_ids:
                    for sm in pk.move_ids_without_package:
                        sm.product_uom_qty = sm.sale_line_id.pfb_quantity
        return res

    def _prepare_invoice(self):

        current_db = self.env.cr.dbname
        # print("current_db", current_db)
        if current_db in ['test_2025_02','test_2025_01','TEST_New','test', 'NPD_S_Group_New_V2', 'NPD_S_Group_New']:
            journal_id = 12
        elif current_db in ['NPD_Bangkok_New']:
            journal_id = 9

        elif current_db in ['NPD_Intertrading_New','NPD_Intertrading_New_NonVat']:
            journal_id = 62

        print("journal_id", journal_id)

        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals['pfb_so_type'] = self.pfb_so_type
        invoice_vals['debt_payment_type'] = self.debt_payment_type
        # invoice_vals['pfb_date_of_rent'] = self.pfb_date_of_rent
        invoice_vals['pfb_objective_id'] = self.pfb_objective_id.id
        invoice_vals['pfb_amount_insurance'] = self.pfb_amount_insurance
        invoice_vals['pfb_dis_amount_insurance'] = self.pfb_dis_amount_insurance
        invoice_vals['pfb_amount'] = self.pfb_amount
        if self.pfb_so_type == 'sale':
            # ค้นหา journal ที่ชื่อ "สมุดรายวันขาย"
            journal = self.env['account.journal'].search([('name', '=', 'สมุดรายวันขาย')], limit=1)
            if not journal:
                raise UserError("ไม่พบสมุดรายวันขาย")
            # print("journal.id",journal.name)
            invoice_vals['journal_id'] = journal.id
        elif self.pfb_so_type == 'rent':
            journal = self.env['account.journal'].search([('name', '=', 'สมุดรายวันเช่า(สาขา)')], limit=1)
            if not journal:
                raise UserError("ไม่พบสมุดรายวันเช่า(สาขา)")
            # print("journal.id",journal.name)
            invoice_vals['journal_id'] = journal.id
        else:
            invoice_vals['journal_id'] = journal_id

        return invoice_vals

        # ฟิลด์เก็บค่าส่วนลดรวมจากรายการที่เป็น 'rental'

    total_rental_discount = fields.Float(
        string="- Rental Discount",
        compute="_compute_total_rental_discount",
        store=True
    )

    @api.depends("order_line.discount_type_selection", "order_line.discount_amount", "discount_amt_line")
    def _compute_total_rental_discount(self):
        for order in self:
            # รวมค่า discount_amount จาก sale.order.line ที่มี discount_type_selection = 'rental'
            order.total_rental_discount = sum(
                (line.discount_amount or 0.0) for line in order.order_line if line.discount_type_selection == 'rental'
            )

            order.discount_amt_line = sum(
                (line.discount_amount or 0.0) for line in order.order_line if not line.discount_type_selection or line.discount_type_selection == 'product'
            )

            # print("🚀 Updated total_rental_discount:", order.total_rental_discount)
            # print("🚀 Updated discount_amt_line:", order.discount_amt_line)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    pfb_so_rent_ok = fields.Boolean('Can be Rent', compute="_compute_so_rent_ok", store=True)
    # pfb_date_of_rent = fields.Integer(string="Day of Rent")
    pfb_date_of_rent = fields.Integer(related='order_id.pfb_date_of_rent', store=True)
    pfb_quantity = fields.Integer(string="Quantity Rent")
    pfb_insurance_price = fields.Float(string="Insurance", compute="_compute_insurance_price", store=True)
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")

    discount_type_selection = fields.Selection(
        [
            ('product', 'ส่วนลดสินค้า'),
            ('rental', 'ส่วนลดค่าเช่า')
        ],
        string="ประเภทส่วนลด",
        default='product'
    )
    second_uom_id = fields.Many2one('uom.uom', string="Secondary UOM")
    second_uom_qty = fields.Float('Secondary Qty')

    is_manual_qty = fields.Boolean(
        string="Manual Quantity Set",
        default=False,
        copy=False,
        store=True,
        help="True if user manually edited product_uom_qty"
    )

    def _prepare_invoice_line(self):
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        print("res_TTTT======", res)
        if self.second_uom_id and self.second_uom_qty:
            res.update({
                'discount_type_selection': self.discount_type_selection
            })
        return res

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.second_uom_qty = self.product_id.weight
        else:
            self.second_uom_qty = 0.0

    @api.onchange('discount_amount')
    def _onchange_discount_amount(self):
        for record in self:
            if record.discount_amount and record.discount_type_selection == 'product':
                max_discount = record.price_subtotal_without_discount * 0.5
                if record.discount_amount > max_discount:
                    return {
                        'warning': {
                            'title': _("แจ้งเตือน!"),
                            'message': _(
                                "ส่วนลดไม่สามารถเกิน 50% ของยอดรวมสินค้าได้ (สูงสุด {:.2f} บาท)."
                                "\nโปรดส่งคำขออนุมัติจากผู้จัดการ.").format(max_discount),
                        }
                    }

    @api.onchange('pfb_quantity', 'pfb_date_of_rent')
    def _onchange_rental_fields(self):
        """เมื่อเปลี่ยน pfb_quantity หรือ pfb_date_of_rent"""
        if self.order_id.pfb_so_type == 'rent':
            self.is_manual_qty = False
            if self.pfb_date_of_rent and self.pfb_quantity:
                self.product_uom_qty = self.pfb_date_of_rent * self.pfb_quantity
                print(f"♻️ รีเซ็ต is_manual_qty และคำนวณ qty ใหม่: {self.product_uom_qty}")

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty_check_manual(self):
        """ตรวจสอบว่าผู้ใช้แก้ไข product_uom_qty ด้วยตนเองหรือไม่"""
        if self.order_id.pfb_so_type == 'rent' and self.pfb_date_of_rent and self.pfb_quantity:
            expected_qty = self.pfb_date_of_rent * self.pfb_quantity
            if abs(self.product_uom_qty - expected_qty) > 0.01:
                self.is_manual_qty = True
                print(f"🔧 ตรวจพบการแก้ไขด้วยตนเอง: {self.product_uom_qty} (คาดหวัง: {expected_qty})")

    @api.depends('product_uom_qty', 'product_id', 'order_id.pfb_date_of_rent', 'pfb_quantity', 'is_manual_qty')
    def _compute_insurance_price(self):
        for so_line in self:
            if so_line.order_id.pfb_so_type == 'rent':
                print("✅ Rental Order")
                if not so_line.is_manual_qty and so_line.pfb_date_of_rent and so_line.pfb_quantity:
                    product_uom_qty_npd = so_line.pfb_date_of_rent * so_line.pfb_quantity
                    print(f"product_uom_qty_npd: {product_uom_qty_npd}, is_manual_qty: {so_line.is_manual_qty}")
                    so_line.product_uom_qty = product_uom_qty_npd

            if so_line.product_id:
                insurance_price = self._compute_insurance_price_rule(
                    [(so_line.product_id, so_line.product_uom_qty, so_line.order_id.partner_id)],
                    date=False, uom_id=False
                )
                so_line.pfb_insurance_price = insurance_price
            else:
                so_line.pfb_insurance_price = 0

            current_db = self.env.cr.dbname
            if current_db != 'NPD_Intertrading_New_NonVat':

                if so_line.order_id.pfb_so_type == 'sale' and so_line.product_id:
                    tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายไม่รวม Vat 7%')], limit=1)
                    if tax:
                        so_line.tax_id = [(6, 0, [tax.id])]

                if so_line.order_id.pfb_so_type == 'rent' and so_line.product_id:
                    tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายยังไม่ถึงกำหนด Vat 7%')], limit=1)
                    if tax:
                        so_line.tax_id = [(6, 0, [tax.id])]

    @api.model
    def create(self, vals):
        line = super(SaleOrderLine, self).create(vals)
        if line.order_id.pfb_so_type == 'rent' and line.pfb_quantity and line.pfb_date_of_rent:
            if not vals.get('is_manual_qty'):
                computed_qty = line.pfb_date_of_rent * line.pfb_quantity
                print(f"📝 Create: คำนวณ qty = {computed_qty}")
                line.write({
                    'product_uom_qty': computed_qty,
                    'is_manual_qty': False
                })
        return line

    def write(self, vals):
        print(f"📝 WRITE CALLED with vals: {vals}")

        if 'product_uom_qty' in vals and 'is_manual_qty' not in vals:
            for line in self:
                if line.order_id.pfb_so_type == 'rent' and line.pfb_date_of_rent and line.pfb_quantity:
                    expected_qty = line.pfb_date_of_rent * line.pfb_quantity
                    if abs(vals['product_uom_qty'] - expected_qty) > 0.01:
                        vals['is_manual_qty'] = True
                        print(f"🔧 บันทึกค่าแก้ไขด้วยตนเอง: {vals['product_uom_qty']} (คาดหวัง: {expected_qty})")

        if 'pfb_quantity' in vals or 'pfb_date_of_rent' in vals:
            vals['is_manual_qty'] = False
            print(f"♻️ รีเซ็ต is_manual_qty")

        result = super(SaleOrderLine, self).write(vals)

        for line in self:
            print(f"✅ หลัง write - product_uom_qty: {line.product_uom_qty}, is_manual_qty: {line.is_manual_qty}")

        return result

    @api.onchange('tax_id')
    def _onchange_tax_id_block(self):
        current_db = self.env.cr.dbname
        if current_db == 'NPD_Intertrading_New_NonVat':
            return
        for line in self:
            if line.order_id.pfb_so_type == 'sale' and line.product_id:
                expected_tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายไม่รวม Vat 7%')], limit=1)
                if expected_tax and set(line.tax_id.ids) != set([expected_tax.id]):
                    line.tax_id = [(6, 0, [expected_tax.id])]
                    return {
                        'warning': {
                            'title': "ไม่สามารถเปลี่ยนภาษี",
                            'message': "อนุญาตเฉพาะภาษีขายไม่รวม Vat 7% สำหรับใบขายเท่านั้น",
                            'type': 'warning'
                        }
                    }

            if line.order_id.pfb_so_type == 'rent' and line.product_id:
                expected_tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายยังไม่ถึงกำหนด Vat 7%')], limit=1)
                if expected_tax and set(line.tax_id.ids) != set([expected_tax.id]):
                    line.tax_id = [(6, 0, [expected_tax.id])]
                    return {
                        'warning': {
                            'title': "ไม่สามารถเปลี่ยนภาษี",
                            'message': "อนุญาตเฉพาะภาษีขายยังไม่ถึงกำหนด Vat 7% สำหรับใบเช่าเท่านั้น",
                            'type': 'warning'
                        }
                    }

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        vals["pfb_quantity"] = self.pfb_quantity
        vals["pfb_date_of_rent"] = self.pfb_date_of_rent
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

    # def _compute_price_rule_get_items(self, products_qty_partner, date, uom_id, prod_tmpl_ids, prod_ids, categ_ids):
    #     self.env['product.pricelist.item'].flush(['price', 'currency_id', 'company_id', 'active'])
    #
    #     # ตรวจสอบว่ามี Pricelist หรือไม่
    #     pricelist_id = self.order_id.pricelist_id.id if self.order_id.pricelist_id else None
    #
    #     # สร้าง SQL Query ตามเงื่อนไข
    #     query = """
    #         SELECT item.id
    #         FROM product_pricelist_item AS item
    #         LEFT JOIN product_category AS categ ON item.categ_id = categ.id
    #         WHERE (item.product_tmpl_id IS NULL OR item.product_tmpl_id = ANY(%s))
    #         AND (item.product_id IS NULL OR item.product_id = ANY(%s))
    #         AND (item.categ_id IS NULL OR item.categ_id = ANY(%s))
    #     """
    #     params = [prod_tmpl_ids, prod_ids, categ_ids]
    #
    #     # เงื่อนไขกรณี Pricelist มีค่า
    #     if pricelist_id:
    #         query += " AND (item.pricelist_id = %s)"
    #         params.append(pricelist_id)
    #     else:
    #         query += " AND (item.pricelist_id IS NULL)"
    #
    #     # เงื่อนไขวันที่
    #     query += """
    #         AND (item.date_start IS NULL OR item.date_start <= %s)
    #         AND (item.date_end IS NULL OR item.date_end >= %s)
    #         AND (item.active = TRUE)
    #         ORDER BY item.applied_on, item.min_quantity DESC, categ.complete_name DESC, item.id DESC
    #     """
    #     params.extend([date, date])
    #
    #     # Execute SQL
    #     self.env.cr.execute(query, params)
    #     item_ids = [x[0] for x in self.env.cr.fetchall()]
    #
    #     return self.env['product.pricelist.item'].browse(item_ids)


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

