from odoo import models, fields, api
from datetime import datetime, timedelta

class MonthlyPenaltyReport(models.Model):
    _name = 'monthly.penalty.report'
    _description = 'สรุปรายงานปรับจำเดือน'

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
    vat_rental_payment_amount  = fields.Float(string="VAT")
    lost_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับหาย")
    damaged_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับชำรุด")

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if not self.env.context.get('no_recursive_update'):
            self = self.with_context(no_recursive_update=True)
            self.generate_report()
        return super(MonthlyPenaltyReport, self).search_read(domain, fields, offset, limit, order)

    @api.model
    def generate_report(self):
        self.sudo().search([]).unlink()

        # วันเดียวกับ SQL
        date_str = '2025-05-13'
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        next_day = date_obj + timedelta(days=1)

        # ✅ ใช้ช่วงเวลาเพื่อแทน DATE(so.date_order) = '2025-05-12'
        sale_orders = self.env['sale.order'].sudo().search([
            ('name', 'like', 'SO-%'),
            ('date_order', '>=', date_obj),
            ('date_order', '<', next_day),
        ])
        # ✅ DEBUG: ตรวจสอบว่าดึง Sale Order ได้ไหม
        print("🧪 วันที่ค้นหา:", date_obj.date())
        print("📦 จำนวน SO ที่พบ:", len(sale_orders))
        print("🧾 รายการ SO:", [so.name for so in sale_orders])

        total_rent = 0
        total_vat = 0
        total_insure = 0
        total_lost = 0
        total_damage = 0
        total_rental_discount = 0
        total_line_discount = 0
        total_net_rental_fee = 0

        total_rental_payment_amount = 0
        total_vat_rental_payment_amount = 0
        total_lost_payment_amount = 0
        total_damaged_payment_amount = 0

        for so in sale_orders:
            total_rent += so.amount_price_subtotal_without_discount or 0
            total_vat += so.amount_tax or 0
            total_insure += so.pfb_amount or 0
            total_rental_discount += so.total_rental_discount or 0

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
                reason = move_l.reason_code_id.name or ''
                if reason == 'ใบแจ้งหนี้ค่าเช่า':
                    total_net_rental_fee += move_l.amount_total or 0

                debt_type = move_l.debt_payment_type or ''
                if debt_type == 'rental':
                    total_rental_payment_amount += move_l.amount_untaxed or 0
                    total_vat_rental_payment_amount += sum(group[1] for group in move_l.amount_by_group or [])

                elif debt_type == 'lost':
                    total_lost_payment_amount += move_l.amount_untaxed or 0
                elif debt_type == 'damaged':
                    total_damaged_payment_amount += move_l.amount_untaxed or 0

        # สร้างบรรทัดเดียวของรายงาน
        if sale_orders:
            self.sudo().create({
                'report_date': date_obj.date(),
                'rental_amount': total_rent,
                'vat': total_vat,
                'insurance': total_insure,
                'lost_penalty': total_lost,
                'damage_penalty': total_damage,
                'rental_discount': total_rental_discount,
                'line_discount': total_line_discount,
                'net_rental_fee': total_net_rental_fee,
                'rental_payment_amount': total_rental_payment_amount,
                'lost_payment_amount': total_lost_payment_amount,
                'damaged_payment_amount': total_damaged_payment_amount,
                'vat_rental_payment_amount': total_vat_rental_payment_amount,
            })
            print("✅ รายงานถูกสร้างแล้ว")
        else:
            print("⚠️ ไม่พบ sale.order ที่ตรงกับเงื่อนไข")
