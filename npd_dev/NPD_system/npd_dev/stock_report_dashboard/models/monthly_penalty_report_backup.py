from odoo import models, fields, api
from datetime import datetime
from collections import defaultdict

class MonthlyPenaltyReport(models.Model):
    _name = 'monthly.penalty.report'
    _description = 'สรุปรายงานประจำเดือน'

    report_date = fields.Date(string='วดป')
    rental_amount = fields.Float(string='ค่าเช่าสินค้า')
    vat = fields.Float(string='VAT')
    insurance = fields.Float(string='ค่าประกัน')
    damage_penalty = fields.Float(string='ค่าปรับชำรุด')
    lost_penalty = fields.Float(string='ค่าปรับหาย')
    rental_discount = fields.Float(string='ส่วนลดค่าเช่า')
    line_discount = fields.Float(string='ส่วนลดปรับหาย')
    net_rental_fee = fields.Float(string='ค่าเช่าสุทธิ')

    rental_payment_amount = fields.Float(string="รับชำระหนี้ค่าเช่า")
    vat_rental_payment_amount = fields.Float(string="VAT")
    lost_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับหาย")
    damaged_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับชำรุด")

    # 🔻 ยอดค้างชำระ
    rental_unpaid_amount = fields.Float(string="ค้างชำระค่าเช่า")
    vat_rental_unpaid_amount = fields.Float(string="ค้าง VAT")
    lost_unpaid_amount = fields.Float(string="ค้างชำระค่าปรับหาย")
    damaged_unpaid_amount = fields.Float(string="ค้างชำระค่าปรับชำรุด")
    difference = fields.Float(string="ส่วนต่าง")

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if not self.env.context.get('no_recursive_update'):
            self = self.with_context(no_recursive_update=True)
            self.generate_report()
        return super(MonthlyPenaltyReport, self).search_read(domain, fields, offset, limit, order)

    @api.model
    def generate_report(self):
        self.sudo().search([]).unlink()
        user_branch = self.env.user.branch_id
        # ✅ ดึง sale.order ทั้งหมด

        if user_branch.name == 'สำนักงานใหญ่':
            sale_orders = self.env['sale.order'].sudo().search([
                ('name', 'like', 'SO-%'),
                ('date_order', '!=', False),

            ])
        else:
            sale_orders = self.env['sale.order'].sudo().search([
                ('name', 'like', 'SO-%'),
                ('date_order', '!=', False),
                ('branch_id', '=', user_branch.id)
            ])

        # ✅ กลุ่มตามวัน
        order_by_date = defaultdict(list)
        for so in sale_orders:
            order_by_date[so.date_order.date()].append(so)

        for report_date, orders in order_by_date.items():
            total_rent = total_vat = total_insure = 0
            total_lost = total_damage = 0
            total_rental_discount = total_line_discount = total_net_rental_fee = 0
            total_rental_payment_amount = total_vat_rental_payment_amount = 0
            total_lost_payment_amount = total_damaged_payment_amount = 0

            total_rental_unpaid_amount = 0
            total_vat_rental_unpaid_amount = 0
            total_lost_unpaid_amount = 0
            total_damaged_unpaid_amount = 0
            total_difference = 0
            total_rent = 0
            rental_per_day = 0
            days_used = 0

            for so in orders:
                total_rent += so.amount_price_subtotal_without_discount or 0
                total_vat += so.amount_tax or 0
                total_insure += so.pfb_amount or 0


                stock_pickings = self.env['stock.picking'].sudo().search([
                    ('group_id.name', '=', so.name),
                    ('state', '=', 'done'),
                    ('name', 'ilike', '%IN%'),
                    ('start_x_date', '!=', False),
                    ('end_x_date', '!=', False),
                ])

                # total_rental_discount += so.total_rental_discount or 0

                for stock in stock_pickings:
                    if stock.approval_state == 'approved':
                        # print("stock.approval_state",stock.approval_state)
                        total_rental_discount += stock.rent_discount or 0

                        # print("stock.total_rental_discount", total_rental_discount)
                    else:
                        total_rental_discount = 0

                    days_used = (1 if (stock.force_date.date() == stock.start_x_date) else (
                                stock.force_date.date() - stock.start_x_date).days)

                    rental_per_day = (so.amount_total) / (
                                        1 if stock.end_x_date == stock.start_x_date else (stock.end_x_date - stock.start_x_date).days)
                    rent_for_this_stock  = rental_per_day * days_used

                    total_rent = rent_for_this_stock

                # print("so.pricelist_id.name",so.pricelist_id.name)
                    if not so.deposit_ref:

                        if so.pricelist_id.name =='เรทเดือน':
                            print("เรทเดือน",stock_pickings.name)
                            dd = (1 if (stock.force_date.date() == stock.start_x_date) else (stock.force_date.date() - stock.start_x_date).days)
                            # print("SO", so.name)
                            # print("dd",dd)
                            if dd < 30:
                                total_difference += 0.00
                            else:
                                total_difference += total_rent - (so.amount_total)
                        else:
                        # print("rental_per_day ", rental_per_day,"days_used ",days_used)
                        # print("total_rent", total_rent)
                          total_difference += total_rent - (so.amount_total)
                    else:

                        total_difference += total_rent - (so.amount_total)
                        # name = stock_pickings.name

                # print("stock_pickings.name", name)
                # print("total_difference",total_difference)

                account_moves = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    ('move_type', '=', 'out_invoice')
                ])
                for move in account_moves:
                    reason = move.reason_code_id.name or ''
                    if reason == 'สินค้าหาย':
                        total_lost += move.wht_amt_net or 0
                        total_line_discount += move.discount_amt_line or 0
                    elif reason == 'สินค้าชำรุด':
                        total_damage += move.wht_amt_net or 0

                account_rental_moves = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    ('payment_state', '=', 'paid')
                ])
                for move_l in account_rental_moves:
                    if move_l.reason_code_id.name == 'ใบแจ้งหนี้ค่าเช่า':
                        total_net_rental_fee += move_l.amount_total or 0

                    debt_type = move_l.debt_payment_type or ''
                    if debt_type == 'rental':
                        total_rental_payment_amount += move_l.amount_untaxed or 0
                        total_vat_rental_payment_amount += sum(g[1] for g in move_l.amount_by_group or [])
                    elif debt_type == 'lost':
                        total_lost_payment_amount += move_l.amount_untaxed or 0
                    elif debt_type == 'damaged':
                        total_damaged_payment_amount += move_l.amount_untaxed or 0

                account_rental_ty_moves = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    '|',
                    ('payment_state', '=', 'not_paid'),
                    ('payment_state', '=', 'partial')
                ])

                for move_ty in account_rental_ty_moves:
                    total_rental_unpaid_amount += move_ty.amount_untaxed or 0
                    total_vat_rental_unpaid_amount += sum(g[1] for g in move_ty.amount_by_group or [])

                account_ty_moves = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    ('move_type', '=', 'out_invoice'),
                    '|',
                    ('payment_state', '=', 'not_paid'),
                    ('payment_state', '=', 'partial')
                ])
                for move_ty in account_ty_moves:
                    reason = move_ty.reason_code_id.name or ''
                    if reason == 'สินค้าหาย':
                        total_lost_unpaid_amount += move_ty.wht_amt_net or 0

                    elif reason == 'สินค้าชำรุด':
                        total_damaged_unpaid_amount += move_ty.wht_amt_net or 0

            # ✅ สร้างบรรทัดรายวัน
            self.sudo().create({
                'report_date': report_date,
                'rental_amount': total_rent,
                'vat': total_vat,
                'insurance': total_insure,
                'lost_penalty': total_lost,
                'damage_penalty': total_damage,
                'rental_discount': total_rental_discount,
                'line_discount': total_line_discount,
                'net_rental_fee': total_net_rental_fee,
                'rental_payment_amount': total_rental_payment_amount,
                'vat_rental_payment_amount': total_vat_rental_payment_amount,
                'lost_payment_amount': total_lost_payment_amount,
                'damaged_payment_amount': total_damaged_payment_amount,
                'rental_unpaid_amount': total_rental_unpaid_amount,
                'vat_rental_unpaid_amount': total_vat_rental_unpaid_amount,
                'lost_unpaid_amount': total_lost_unpaid_amount,
                'damaged_unpaid_amount': total_damaged_unpaid_amount,
                'difference': total_difference,
            })

            # ✅ แสดงผล debug
            # print("🧪 วันที่:", report_date)
            # print("📦 จำนวน SO:", len(orders))
            # print("🧾 รายการ:", [s.name for s in orders])
            # print("✔️ รายงานถูกสร้าง\n")
