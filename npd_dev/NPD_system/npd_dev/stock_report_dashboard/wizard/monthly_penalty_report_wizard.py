from odoo import models, fields, api
from datetime import datetime, timedelta
from collections import defaultdict


class MonthlyPenaltyReportWizard(models.TransientModel):
    _name = 'monthly.penalty.report.wizard'
    _description = 'Wizard สำหรับสรุปรายงานประจำเดือน'

    date_from = fields.Date(
        string='วันที่เริ่มต้น',
        help='เว้นว่างเพื่อดูข้อมูลทั้งหมด'
    )
    date_to = fields.Date(
        string='วันที่สิ้นสุด',
        default=fields.Date.today,
        help='เว้นว่างเพื่อดูข้อมูลทั้งหมด'
    )
    branch_ids = fields.Many2many(
        'res.branch',
        string='สาขา',
        help='เว้นว่างเพื่อดูทุกสาขา'
    )

    # ✅ เพิ่มหลัง branch_ids
    contact_type = fields.Selection([
        ('branch', 'สาขา'),
        ('sale', 'Sale')
    ], string='ประเภท Contact', help='เว้นว่างเพื่อดูทุกประเภท')

    def action_generate_report(self):
        """สร้างรายงานตามเงื่อนไขที่เลือก"""
        # ลบข้อมูลเก่าทั้งหมด
        self.env['monthly.penalty.report'].sudo().search([]).unlink()

        # สร้าง domain สำหรับค้นหา Sale Orders
        domain = [
            ('state', 'not in', ('draft', 'sent', 'cancel')),
            ('pfb_so_type', '=', 'rent'),
            ('name', 'like', 'SO%'),
            ('rental_status', '!=', 'ready')
        ]

        # เพิ่มเงื่อนไขวันที่ (ใช้ <= แทน <)
        if self.date_from:
            domain.append(('date_order', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_order', '<=', self.date_to))

        # เพิ่มเงื่อนไขสาขา
        if self.branch_ids:
            domain.append(('branch_id', 'in', self.branch_ids.ids))

        if self.contact_type:
            domain.append(('contact_type', '=', self.contact_type))

        # ✅ แก้ไข: ใช้ sudo() อย่างถูกต้อง และรวม domain เข้าด้วยกัน
        sale_orders = self.env['sale.order'].sudo().search(domain)

        # 🔍 DEBUG: พิมพ์ domain และจำนวน results
        print(f"\n{'=' * 60}")
        print(f"🔍 DEBUG: Domain ที่ใช้:")
        print(domain)
        print(f"📊 พบ Sale Orders: {len(sale_orders)} รายการ")
        print(f"{'=' * 60}\n")

        if not sale_orders:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'แจ้งเตือน',
                    'message': 'ไม่พบข้อมูลตามเงื่อนไขที่กำหนด',
                    'type': 'info',
                    'sticky': False,
                }
            }

        # กลุ่มตามวัน
        order_by_date = defaultdict(list)
        for so in sale_orders:
            order_by_date[so.date_order.date()].append(so)

        # เตรียมข้อมูลที่จะสร้าง
        records_to_create = []

        # 🔧 เก็บ payment ที่มีวันที่ต่างจาก report_date
        deferred_payments = {}  # {'2025-11-20': {'rental': 2000.75, 'vat': 141.48, ...}}

        # 🔧 เรียงลำดับ report_date ให้เป็นลำดับวันที่ (เก่า → ใหม่)
        sorted_report_dates = sorted(order_by_date.keys())

        for report_date in sorted_report_dates:
            orders = order_by_date[report_date]
            total_rent_s = total_vat = total_insure = 0
            total_lost = total_damage = 0
            total_rental_discount = total_line_discount = total_net_rental_fee = 0
            total_rental_payment_amount = total_vat_rental_payment_amount = 0
            total_lost_payment_amount = total_damaged_payment_amount = 0
            total_rental_unpaid_amount = 0
            total_vat_rental_unpaid_amount = 0
            total_lost_unpaid_amount = 0
            total_damaged_unpaid_amount = 0
            total_difference = 0
            count_all = 0
            total_all = 0
            # เตรียมตัวแปรรวมสำหรับ payment amounts ที่ loop แต่ละ SO
            total_rental_payment_amount = 0.0
            total_vat_rental_payment_amount = 0.0
            total_lost_payment_amount = 0.0
            total_damaged_payment_amount = 0.0

            for so in orders:
                total_rent_s += so.amount_untaxed or 0
                total_vat += so.amount_tax or 0
                if not so.deposit_ref:
                    total_insure += so.pfb_amount or 0

                # Stock Pickings
                stock_pickings = self.env['stock.picking'].sudo().search([
                    ('group_id.name', '=', so.name),
                    ('state', '=', 'done'),
                    ('name', 'ilike', '%IN%'),
                    ('start_x_date', '!=', False),
                    ('end_x_date', '!=', False),
                ])

                for stock in stock_pickings:
                    if stock.approval_state == 'approved':
                        total_rental_discount += stock.rent_discount or 0

                    days_used = (1 if (stock.return_date.date() == stock.start_x_date) else (
                            stock.return_date.date() - stock.start_x_date).days)

                    billed_days = 1 if stock.end_x_date == stock.start_x_date else (stock.end_x_date - stock.start_x_date).days
                    rental_per_day = round(so.amount_total / billed_days, 2)
                    rent_for_this_stock = rental_per_day * days_used
                    total_rent = rent_for_this_stock

                    # คำนวณค่าเช่าส่วนต่าง (value_16 ใน XML)
                    value_16 = rental_per_day * (days_used - billed_days)

                    if not so.deposit_ref:
                        # บิลที่ไม่ต่ออายุ (deposit_count == 0)

                        # ✅ เช็คว่า SO นี้ถูกอ้างอิงใน deposit_ref ของ SO อื่นหรือไม่
                        is_referenced_by_other = self.env['sale.order'].sudo().search([
                            ('deposit_ref', '=', so.name),
                            ('state', '=', 'sale')
                        ], limit=1)

                        # ✅ เช็คโปรโมชั่นส่งฟรีก่อน
                        campaign_name = getattr(so.campaign_id, 'name', '') or ''

                        if campaign_name in ['โปร 2026 ส่งฟรีไม่เกิน 25 Km.', 'โปร 2026 ส่งฟรีไม่เกิน 35 Km.']:
                            today_date = fields.Date.today()
                            if today_date > stock.end_x_date:
                                total_difference += value_16
                                print(
                                    f"  - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน > end_x_date → total_difference += {value_16}")
                            else:
                                total_difference += 0.00
                                print(
                                    f"  - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน <= end_x_date → total_difference += 0.00")

                        elif 'เรทเดือน' in (so.pricelist_id.name or ''):
                            dd = (1 if (stock.return_date.date() == stock.start_x_date) else (
                                    stock.return_date.date() - stock.start_x_date).days)
                            # print(f"  - pricelist contains เรทเดือน, dd = {dd}")

                            # ✅ ไม่มี deposit_ref และไม่ถูก SO อื่นอ้างอิง
                            if not so.deposit_ref and not is_referenced_by_other and stock.return_date.date() <= stock.end_x_date:
                                total_difference += 0.00
                                # print(f"  - ไม่ถูกอ้างอิง → total_difference += 0.00")

                                # ✅ ไม่มี deposit_ref แต่ถูก SO อื่นอ้างอิง (SO ต้นทางที่ถูกต่ออายุ)
                            elif not so.deposit_ref and not is_referenced_by_other and stock.return_date.date() > stock.end_x_date:
                                total_difference += value_16
                                # print(
                                #     f"  - ถูกอ้างอิงโดย {is_referenced_by_other.name} → total_difference += {value_16}")

                            elif not so.deposit_ref and is_referenced_by_other and stock.return_date.date() > stock.end_x_date:
                                total_difference += value_16
                                # print(
                                #     f"  - ถูกอ้างอิงโดย {is_referenced_by_other.name} → total_difference += {value_16}")


                            # ✅ ไม่มี deposit_ref แต่ถูก SO อื่นอ้างอิง (SO ต้นทางที่ถูกต่ออายุ)
                            elif not so.deposit_ref and is_referenced_by_other:
                                total_difference += 0.00
                                # total_difference += value_16
                                # print(
                                #     f"  - ถูกอ้างอิงโดย {is_referenced_by_other.name} → total_difference += {value_16}")

                            else:
                                if dd < 30:
                                    total_difference += 0.00
                                    # print(f"  - dd < 30 → total_difference += 0.00")
                                else:
                                    total_difference += value_16
                                    # print(f"  - dd >= 30 → total_difference += {value_16}")
                        else:
                            total_difference += value_16
                            # print(f"  - pricelist ≠ เรทเดือน → total_difference += {value_16}")
                    else:
                        # บิลที่ต่ออายุ (มี deposit_ref)
                        deposit_ref = so.deposit_ref or ''

                        # ✅ ดึงทุก ref จาก deposit_ref (ไม่ใช่แค่ตัวสุดท้าย)
                        deposit_refs = [ref.strip() for ref in deposit_ref.split(',')] if deposit_ref else []

                        print(f"\n{'=' * 60}")
                        print(f"🔍 DEBUG: คำนวณ total_difference (Report)")
                        print(f"{'=' * 60}")
                        print(f"  - SO: {so.name}")
                        print(f"  - deposit_ref: {deposit_ref}")
                        print(f"  - deposit_refs (list): {deposit_refs}")

                        # ✅ ค้นหา stock.picking ทั้งหมดจากทุก ref
                        related_pickings = self.env['stock.picking'].sudo().search([
                            ('group_id.name', 'in', deposit_refs)
                        ])

                        print(f"  - found pickings: {len(related_pickings)} รายการ")
                        for rp in related_pickings:
                            print(f"    - {rp.name} | group: {rp.group_id.name} | end_x_date: {rp.end_x_date}")

                        # ✅ เช็คว่ามี end_x_date ที่ != stock.end_x_date หรือไม่
                        # มี = 1 (มีความแตกต่าง), ไม่มี = 0 (ทุกตัวเท่ากัน)
                        has_diff_end_date = 0
                        if related_pickings:
                            for rp in related_pickings:
                                if rp.end_x_date != stock.end_x_date:
                                    has_diff_end_date = 1
                                    break

                        print(f"  - current end_x_date: {stock.end_x_date}")
                        print(
                            f"  - has_diff_end_date: {has_diff_end_date} {'(มีความแตกต่าง)' if has_diff_end_date == 1 else '(ทุกตัวเท่ากัน)'}")

                        if related_pickings:
                            # ✅ ใช้ has_diff_end_date == 0 แทน prev_end_x_date == stock.end_x_date
                            if has_diff_end_date == 0 and stock.return_date.date() <= stock.end_x_date:
                                print(f"\n  📍 SUB-CASE: ทุก end_x_date เท่ากัน และ วันที่คืน <= วันสิ้นสุด")

                                # ✅ เช็คโปรโมชั่นส่งฟรีก่อน
                                campaign_name = getattr(so.campaign_id, 'name', '') or ''

                                if campaign_name in ['โปร 2026 ส่งฟรีไม่เกิน 25 Km.', 'โปร 2026 ส่งฟรีไม่เกิน 35 Km.']:
                                    today_date = fields.Date.today()
                                    if today_date > stock.end_x_date:
                                        total_difference += value_16
                                        print(
                                            f"    - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน > end_x_date → total_difference += {value_16}")
                                    else:
                                        total_difference += 0.00
                                        print(
                                            f"    - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน <= end_x_date → total_difference += 0.00")

                                # end_x_date เท่ากัน
                                elif 'เรทเดือน' in (so.pricelist_id.name or ''):
                                    dd = (1 if (stock.return_date.date() == stock.start_x_date) else (
                                            stock.return_date.date() - stock.start_x_date).days)
                                    print(f"    - pricelist contains เรทเดือน, dd = {dd}")

                                    if dd < 30:
                                        total_difference += 0.00
                                        print(f"    - dd < 30 → total_difference += 0.00")
                                    else:
                                        total_difference += value_16
                                        print(f"    - dd >= 30 → total_difference += {value_16}")
                                else:
                                    total_difference += value_16
                                    print(f"    - pricelist ≠ เรทเดือน → total_difference += {value_16}")
                            else:
                                # มี end_x_date ที่ต่างกัน หรือ วันที่คืน > วันสิ้นสุด
                                print(f"\n  📍 SUB-CASE: มี end_x_date ที่ต่างกัน หรือ วันที่คืน > วันสิ้นสุด")
                                total_difference += value_16
                                print(f"    - total_difference += {value_16}")
                        else:
                            # ไม่พบ related_pickings → ใช้ value_16 ปกติ
                            print(f"\n  📍 SUB-CASE: ไม่พบ related_pickings")
                            total_difference += value_16
                            print(f"    - total_difference += {value_16}")

                        print(f"\n  ✅ RESULT: total_difference = {total_difference}")
                        print(f"{'=' * 60}\n")

                # for stock in stock_pickings:
                #     if stock.approval_state == 'approved':
                #         total_rental_discount += stock.rent_discount or 0
                #
                #     days_used = (1 if (stock.return_date.date() == stock.start_x_date) else (
                #             stock.return_date.date() - stock.start_x_date).days)
                #
                #     rental_per_day = (so.amount_total) / (
                #         1 if stock.end_x_date == stock.start_x_date else (stock.end_x_date - stock.start_x_date).days)
                #     rent_for_this_stock = rental_per_day * days_used
                #     total_rent = rent_for_this_stock
                #
                #     # คำนวณค่าเช่าส่วนต่าง (value_16 ใน XML)
                #     value_16 = total_rent - so.amount_total
                #
                #     if not so.deposit_ref:
                #         # บิลที่ไม่ต่ออายุ (deposit_count == 0)
                #         if so.pricelist_id.name == 'เรทเดือน':
                #             dd = (1 if (stock.return_date.date() == stock.start_x_date) else (
                #                     stock.return_date.date() - stock.start_x_date).days)
                #             if not so.deposit_ref:
                #                 total_difference += 0.00
                #             else:
                #                 if dd < 30:
                #                     total_difference += 0.00
                #                 else:
                #                     total_difference += value_16
                #         else:
                #             total_difference += value_16
                #     else:
                #         # บิลที่ต่ออายุ (มี deposit_ref)
                #         deposit_ref = so.deposit_ref or ''
                #         last_deposit_ref = deposit_ref.split(',')[-1].strip() if deposit_ref else ''
                #
                #         # ค้นหา stock.picking ที่มี group_id.name ตรงกับค่าล่าสุด
                #         related_picking = self.env['stock.picking'].sudo().search([
                #             ('group_id.name', '=', last_deposit_ref)
                #         ], limit=1)
                #
                #         if related_picking:
                #             prev_end_x_date = related_picking.end_x_date
                #
                #             if prev_end_x_date == stock.end_x_date and stock.return_date.date() <= stock.end_x_date:
                #                 # end_x_date เท่ากัน
                #                 if so.pricelist_id.name == 'เรทเดือน':
                #                     dd = (1 if (stock.return_date.date() == stock.start_x_date) else (
                #                             stock.return_date.date() - stock.start_x_date).days)
                #                     if dd < 30:
                #                         total_difference += 0.00
                #                     else:
                #                         total_difference += value_16
                #                 else:
                #                     total_difference += value_16
                #             else:
                #                 # end_x_date ไม่เท่ากัน
                #                 total_difference += value_16
                #         else:
                #             # ไม่พบ related_picking → ใช้ value_16 ปกติ
                #             total_difference += value_16

                # Account Moves - ค่าปรับ
                # account_moves = self.env['account.move'].sudo().search([
                #     ('invoice_origin', '=', so.name),
                #     ('invoice_date', '=', so.date_order.date()),
                #     ('name', 'like', 'INV-%'),
                #     ('move_type', '=', 'out_invoice')
                # ])
                #
                # for move in account_moves:
                #     # ตรวจสอบเฉพาะที่มีการชำระ
                #     if move.payment_state in ['partial', 'paid']:
                #
                #         # ดึง partial reconciles
                #         partial_reconciles = self.env['account.partial.reconcile'].sudo().search([
                #             '|',
                #             ('debit_move_id.move_id', '=', move.id),
                #             ('credit_move_id.move_id', '=', move.id)
                #         ], order='create_date asc')
                #
                #         # ✅ แสดงเฉพาะที่ตรงเงื่อนไข: ยอดค้าง > 0 และมีการชำระ > 1 รายการ
                #         if move.amount_residual > 0 and len(partial_reconciles) > 1:
                #             # print(f"\n{'=' * 60}")
                #             # print(f"เลขที่เอกสาร: {move.name}")
                #             # print(f"สถานะการชำระ: {move.payment_state}")
                #             # print(f"ยอดรวม: {move.amount_total:,.2f} บาท")
                #             # print(f"ยอดค้างชำระ: {move.amount_residual:,.2f} บาท")
                #             # print(f"ยอดที่ชำระแล้ว: {move.amount_total - move.amount_residual:,.2f} บาท")
                #             #
                #             # print(f"\n📋 รายการชำระล่าสุด (จากทั้งหมด {len(partial_reconciles)} รายการ):")
                #             # print("-" * 50)
                #
                #             # ดึงรายการล่าสุด (รายการท้ายสุด)
                #             latest_pr = partial_reconciles[-1]
                #
                #             # หาเอกสารการชำระเงิน
                #             if latest_pr.credit_move_id.move_id.id != move.id:
                #                 payment_move = latest_pr.credit_move_id.move_id
                #                 payment_line = latest_pr.credit_move_id
                #             else:
                #                 payment_move = latest_pr.debit_move_id.move_id
                #                 payment_line = latest_pr.debit_move_id
                #
                #             # แสดงรายละเอียดการชำระล่าสุด
                #             # print(f"    📄 เอกสารชำระ: {payment_move.name}")
                #             # print(f"    📅 วันที่ชำระ: {payment_move.date}")
                #             # print(f"    💰 จำนวนเงิน: {latest_pr.amount:,.2f} บาท")
                #
                #             total_rental_payment_amount += latest_pr.amount
                #
                #             # ✅ เพิ่ม: คำนวณยอดหัก VAT 7%
                #             vat_rate = 7  # VAT 7%
                #             amount_without_vat = latest_pr.amount * (100 / (100 + vat_rate))
                #             vat_amount = latest_pr.amount - amount_without_vat
                #             # print(f"    💰 VAT 7% : {vat_amount:,.2f} บาท")
                #             total_vat_rental_payment_amount += vat_amount
                #
                #             # หา Payment ถ้ามี
                #             # if payment_line.payment_id:
                #             #     print(f"    🏦 วิธีชำระ: {payment_line.payment_id.journal_id.name}")
                #             #     print(f"    📝 อ้างอิง: {payment_line.payment_id.ref or '-'}")
                #             #
                #             # print("-" * 50)
                #             # print(f"  💳 ยังคงค้างชำระ: {move.amount_residual:,.2f} บาท")
                #             # print("=" * 60)
                #
                #         # ไม่ตรงเงื่อนไข = ไม่แสดงอะไรเลย (ข้ามไป)
                #         else:
                #             continue

                account_moves = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    ('state', '=', 'posted'),
                    ('name', 'like', 'INV-%'),
                    ('move_type', '=', 'out_invoice')
                ])

                for move in account_moves:
                    # ตรวจสอบเฉพาะที่มีการชำระ
                    if move.payment_state in ['partial', 'paid']:

                        # ดึง partial reconciles
                        partial_reconciles = self.env['account.partial.reconcile'].sudo().search([
                            '|',
                            ('debit_move_id.move_id', '=', move.id),
                            ('credit_move_id.move_id', '=', move.id)
                        ], order='create_date asc')

                        debit_payments = partial_reconciles.mapped('debit_move_id.payment_id')
                        credit_payments = partial_reconciles.mapped('credit_move_id.payment_id')
                        all_payments = (debit_payments | credit_payments)  # union recordset

                        # ดึงวันที่จาก account.payment (field = date)
                        payment_dates_raw = all_payments.mapped('date')  # ได้เป็น list ของ datetime.date

                        # 🔧 แปลง datetime.date ให้เป็น date string (YYYY-MM-DD)
                        payment_dates = [str(d) if d else None for d in payment_dates_raw]
                        invoice_date_str = str(move.invoice_date)  # แปลง invoice_date เป็น string
                        report_date_str = str(report_date)  # แปลง report_date เป็น string

                        print(f"📅 Invoice Date: {invoice_date_str}")
                        print(f"📅 Report Date: {report_date_str}")
                        print(f"💳 Payment Dates: {payment_dates}")
                        print(f"📊 Total Partial Reconciles: {len(partial_reconciles)}\n")

                        # ✅ เงื่อนไข 1: ชำระในวันเดียวกับ invoice_date
                        invoice_date_payments = [pr for pr in partial_reconciles
                                                 if str(pr.debit_move_id.payment_id.date) == invoice_date_str or
                                                 str(pr.credit_move_id.payment_id.date) == invoice_date_str]

                        count_invoice_date = len(invoice_date_payments)

                        print(f"✅ Invoice Date Payments: {count_invoice_date}")

                        if count_invoice_date == 1:
                            print(f"❌ Skip: Only 1 payment on invoice date")

                        elif count_invoice_date == 2:
                            print(f"✅ Show: Latest payment (2 total on invoice date)")
                            if invoice_date_payments:
                                latest_pr = invoice_date_payments[-1]
                                total_rental_payment_amount += latest_pr.amount

                                vat_rate = 7
                                amount_without_vat = latest_pr.amount * (100 / (100 + vat_rate))
                                vat_amount = latest_pr.amount - amount_without_vat
                                total_vat_rental_payment_amount += vat_amount

                        elif count_invoice_date >= 3:
                            print(f"✅ Show: Sum from 2nd payment onwards (3+ on invoice date)")
                            if len(invoice_date_payments) >= 2:
                                for pr in invoice_date_payments[1:]:
                                    total_rental_payment_amount += pr.amount

                                    vat_rate = 7
                                    amount_without_vat = pr.amount * (100 / (100 + vat_rate))
                                    vat_amount = pr.amount - amount_without_vat
                                    total_vat_rental_payment_amount += vat_amount

                        # ✅ เงื่อนไข 2: ชำระในวันต่างกับ invoice_date
                        # 🔧 แก้: แยกการชำระตามวันที่ payment และหากเป็น report_date ปัจจุบัน ให้แสดง
                        other_date_payments_all = []
                        payment_date_dict = {}

                        for pr in partial_reconciles:
                            # หา payment_date จาก debit หรือ credit
                            debit_payment_date = str(
                                pr.debit_move_id.payment_id.date) if pr.debit_move_id.payment_id else None
                            credit_payment_date = str(
                                pr.credit_move_id.payment_id.date) if pr.credit_move_id.payment_id else None

                            # เลือกวันที่ที่ไม่ใช่ invoice_date
                            payment_date = debit_payment_date or credit_payment_date

                            if payment_date and payment_date != invoice_date_str and payment_date != 'False':
                                other_date_payments_all.append(pr)

                                # จัดกลุ่มตามวันที่
                                if payment_date not in payment_date_dict:
                                    payment_date_dict[payment_date] = []
                                payment_date_dict[payment_date].append(pr)

                        print(f"✅ Other Date Payments (breakdown by date): {payment_date_dict}")
                        print(f"✅ Report Date: {report_date_str}\n")

                        # ✅ เงื่อนไข 2: ตรวจสอบ payment ในแต่ละวัน
                        for payment_date, payments_list in payment_date_dict.items():
                            count = len(payments_list)
                            print(f"  📅 Payment Date: {payment_date}, Count: {count}")

                            # 🔧 แก้: ถ้า payment_date == report_date ให้แสดง ไม่ว่าจะมีกี่ยอด
                            if payment_date == report_date_str:
                                print(f"  ✅ Show: Payment on report date (sum {count} payments)\n")
                                for pr in payments_list:
                                    total_rental_payment_amount += pr.amount

                                    vat_rate = 7
                                    amount_without_vat = pr.amount * (100 / (100 + vat_rate))
                                    vat_amount = pr.amount - amount_without_vat
                                    total_vat_rental_payment_amount += vat_amount
                            else:
                                # 🔧 เก็บ payment ไว้สำหรับวัน report_date ที่จะมาถึง
                                print(f"  💾 Defer: Save for report_date {payment_date}\n")
                                # if payment_date not in deferred_payments:
                                #     deferred_payments[payment_date] = {
                                #         'rental': 0.0,
                                #         'vat': 0.0,
                                #     }
                                if payment_date not in deferred_payments:
                                    deferred_payments[payment_date] = {
                                        'rental': 0.0,
                                        'vat': 0.0,
                                        'lost': 0.0,
                                        'damaged': 0.0,
                                    }

                                for pr in payments_list:
                                    deferred_payments[payment_date]['rental'] += pr.amount
                                    vat_rate = 7
                                    amount_without_vat = pr.amount * (100 / (100 + vat_rate))
                                    vat_amount = pr.amount - amount_without_vat
                                    deferred_payments[payment_date]['vat'] += vat_amount

                # 🔧 หมายเหตุ: ไม่รีเซ็ต total_lost_payment_amount และ total_damaged_payment_amount
                # เพื่อให้รวมสะสมจากทุก move
                account_moves_types = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    ('state', '=', 'posted'),
                    ('move_type', '=', 'out_invoice'),
                    '|',  # ← OR
                    ('name', 'like', 'ILS-%'),
                    ('name', 'like', 'IBK-%'),
                ])

                for move in account_moves_types:
                    # ตรวจสอบเฉพาะที่มีการชำระ
                    if move.payment_state in ['partial', 'paid']:

                        reason = move.reason_code_id.name or ''
                        if reason == 'สินค้าหาย':
                            total_lost += move.wht_amt_net or 0
                            total_line_discount += move.discount_amount_computed or 0
                        elif reason == 'สินค้าชำรุด':
                            total_damage += move.wht_amt_net or 0

                        # ดึง partial reconciles
                        partial_reconciles = self.env['account.partial.reconcile'].sudo().search([
                            '|',
                            ('debit_move_id.move_id', '=', move.id),
                            ('credit_move_id.move_id', '=', move.id)
                        ], order='create_date asc')

                        debit_payments = partial_reconciles.mapped('debit_move_id.payment_id')
                        credit_payments = partial_reconciles.mapped('credit_move_id.payment_id')
                        all_payments = (debit_payments | credit_payments)

                        # แปลง payment_dates เป็น string เพื่อเปรียบเทียบ
                        payment_dates_raw = all_payments.mapped('date')
                        payment_dates = [str(d) if d else None for d in payment_dates_raw]
                        invoice_date_str = str(move.invoice_date)
                        report_date_str = str(report_date)

                        print(f"📅 Invoice Date: {invoice_date_str}")
                        print(f"📅 Report Date: {report_date_str}")
                        print(f"💳 Payment Dates: {payment_dates}")
                        print(f"🏷️  Reason: {reason}\n")

                        # ========== สินค้าหาย ==========
                        if reason == 'สินค้าหาย':
                            # ✅ เงื่อนไข 1: ชำระในวันเดียวกับ invoice_date
                            invoice_date_payments = [pr for pr in partial_reconciles
                                                     if str(pr.debit_move_id.payment_id.date) == invoice_date_str or
                                                     str(pr.credit_move_id.payment_id.date) == invoice_date_str]

                            count_invoice_date = len(invoice_date_payments)

                            print(f"✅ Lost - Invoice Date Payments: {count_invoice_date}")

                            if count_invoice_date == 1:
                                print(f"❌ Skip: Only 1 payment on invoice date")

                            elif count_invoice_date == 2:
                                print(f"✅ Show: Latest payment (2 total on invoice date)")
                                if invoice_date_payments:
                                    latest_pr = invoice_date_payments[-1]
                                    total_lost_payment_amount += latest_pr.amount

                            elif count_invoice_date >= 3:
                                print(f"✅ Show: Sum from 2nd payment onwards (3+ on invoice date)")
                                if len(invoice_date_payments) >= 2:
                                    for pr in invoice_date_payments[1:]:
                                        total_lost_payment_amount += pr.amount

                            # ✅ เงื่อนไข 2: ชำระในวันต่างกับ invoice_date
                            other_date_payments_all = []
                            payment_date_dict = {}

                            for pr in partial_reconciles:
                                # หา payment_date จาก debit หรือ credit
                                debit_payment_date = str(
                                    pr.debit_move_id.payment_id.date) if pr.debit_move_id.payment_id else None
                                credit_payment_date = str(
                                    pr.credit_move_id.payment_id.date) if pr.credit_move_id.payment_id else None

                                # เลือกวันที่ที่ไม่ใช่ invoice_date
                                payment_date = debit_payment_date or credit_payment_date

                                if payment_date and payment_date != invoice_date_str and payment_date != 'False':
                                    other_date_payments_all.append(pr)

                                    # จัดกลุ่มตามวันที่
                                    if payment_date not in payment_date_dict:
                                        payment_date_dict[payment_date] = []
                                    payment_date_dict[payment_date].append(pr)

                            print(f"✅ Other Date Payments (breakdown by date): {payment_date_dict}\n")

                            # ตรวจสอบ payment ในแต่ละวัน
                            for payment_date, payments_list in payment_date_dict.items():
                                count = len(payments_list)
                                print(f"  📅 Payment Date: {payment_date}, Count: {count}")

                                if payment_date == report_date_str:
                                    print(f"  ✅ Show: Payment on report date (sum {count} payments)\n")
                                    for pr in payments_list:
                                        total_lost_payment_amount += pr.amount
                                else:
                                    # payment_date != report_date → เก็บใน deferred
                                    print(f"  💾 Defer: Save for report_date {payment_date}\n")
                                    if payment_date not in deferred_payments:
                                        deferred_payments[payment_date] = {
                                            'rental': 0.0,
                                            'vat': 0.0,
                                            'lost': 0.0,
                                            'damaged': 0.0,
                                        }
                                    # 🔧 ensure all keys exist
                                    if 'lost' not in deferred_payments[payment_date]:
                                        deferred_payments[payment_date]['lost'] = 0.0
                                    if 'damaged' not in deferred_payments[payment_date]:
                                        deferred_payments[payment_date]['damaged'] = 0.0

                                    for pr in payments_list:
                                        deferred_payments[payment_date]['lost'] += pr.amount

                            # ========== สินค้าชำรุด ==========
                        elif reason == 'สินค้าชำรุด':
                            # ✅ เงื่อนไข 1: ชำระในวันเดียวกับ invoice_date
                            invoice_date_payments = [pr for pr in partial_reconciles
                                                     if str(pr.debit_move_id.payment_id.date) == invoice_date_str or
                                                     str(pr.credit_move_id.payment_id.date) == invoice_date_str]

                            count_invoice_date = len(invoice_date_payments)

                            print(f"✅ Damaged - Invoice Date Payments: {count_invoice_date}")

                            if count_invoice_date == 1:
                                print(f"❌ Skip: Only 1 payment on invoice date")

                            elif count_invoice_date == 2:
                                print(f"✅ Show: Latest payment (2 total on invoice date)")
                                if invoice_date_payments:
                                    latest_pr = invoice_date_payments[-1]
                                    total_damaged_payment_amount += latest_pr.amount

                            elif count_invoice_date >= 3:
                                print(f"✅ Show: Sum from 2nd payment onwards (3+ on invoice date)")
                                if len(invoice_date_payments) >= 2:
                                    for pr in invoice_date_payments[1:]:
                                        total_damaged_payment_amount += pr.amount

                            # ✅ เงื่อนไข 2: ชำระในวันต่างกับ invoice_date
                            other_date_payments_all = []
                            payment_date_dict = {}

                            for pr in partial_reconciles:
                                # หา payment_date จาก debit หรือ credit
                                debit_payment_date = str(
                                    pr.debit_move_id.payment_id.date) if pr.debit_move_id.payment_id else None
                                credit_payment_date = str(
                                    pr.credit_move_id.payment_id.date) if pr.credit_move_id.payment_id else None

                                # เลือกวันที่ที่ไม่ใช่ invoice_date
                                payment_date = debit_payment_date or credit_payment_date

                                if payment_date and payment_date != invoice_date_str and payment_date != 'False':
                                    other_date_payments_all.append(pr)

                                    # จัดกลุ่มตามวันที่
                                    if payment_date not in payment_date_dict:
                                        payment_date_dict[payment_date] = []
                                    payment_date_dict[payment_date].append(pr)

                            print(f"✅ Other Date Payments (breakdown by date): {payment_date_dict}\n")

                            # ตรวจสอบ payment ในแต่ละวัน
                            for payment_date, payments_list in payment_date_dict.items():
                                count = len(payments_list)
                                print(f"  📅 Payment Date: {payment_date}, Count: {count}")

                                if payment_date == report_date_str:
                                    print(f"  ✅ Show: Payment on report date (sum {count} payments)\n")
                                    for pr in payments_list:
                                        total_damaged_payment_amount += pr.amount
                                else:
                                    # payment_date != report_date → เก็บใน deferred
                                    print(f"  💾 Defer: Save for report_date {payment_date}\n")
                                    if payment_date not in deferred_payments:
                                        deferred_payments[payment_date] = {
                                            'rental': 0.0,
                                            'vat': 0.0,
                                            'lost': 0.0,
                                            'damaged': 0.0,
                                        }
                                    # 🔧 ensure all keys exist
                                    if 'lost' not in deferred_payments[payment_date]:
                                        deferred_payments[payment_date]['lost'] = 0.0
                                    if 'damaged' not in deferred_payments[payment_date]:
                                        deferred_payments[payment_date]['damaged'] = 0.0

                                    for pr in payments_list:
                                        deferred_payments[payment_date]['damaged'] += pr.amount

                # Account Moves - รับชำระ
                # account_rental_moves = self.env['account.move'].sudo().search([
                #     ('invoice_origin', '=', so.name),
                #     ('payment_state', '=', 'paid'),
                #     ('name', 'like', 'INV-%'),
                # ])
                # for move_l in account_rental_moves:
                #     if move_l.reason_code_id.name == 'ใบแจ้งหนี้ค่าเช่า':
                #         print("สถานะ ", move_l.payment_state)
                #         print("so ",move_l.name)
                #         print("ราคา ", move_l.amount_total)
                #
                #         print("=====================================")
                #
                #         total_net_rental_fee += move_l.amount_total or 0

                #
                #     debt_type = move_l.debt_payment_type or ''
                #     if debt_type == 'rental':
                #         total_rental_payment_amount += move_l.amount_untaxed or 0
                #         total_vat_rental_payment_amount += sum(g[1] for g in move_l.amount_by_group or [])
                #     elif debt_type == 'lost':
                #         total_lost_payment_amount += move_l.amount_untaxed or 0
                #     elif debt_type == 'damaged':
                #         total_damaged_payment_amount += move_l.amount_untaxed or 0

                # Account Moves - ค้างชำระ
                account_rental_ty_moves = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    ('state', '=', 'posted'),
                    '|',
                    ('payment_state', '=', 'not_paid'),
                    ('payment_state', '=', 'partial'),
                    ('state', '!=', 'cancel'),  # 🔧 ไม่รวม ใบแจ้งหนี้ที่ยกเลิก
                ])
                for move_ty in account_rental_ty_moves:
                    if move_ty.payment_state == 'not_paid':
                        total_rental_unpaid_amount += move_ty.amount_untaxed or 0
                        total_vat_rental_unpaid_amount += sum(g[1] for g in move_ty.amount_by_group or [])
                    elif move_ty.payment_state == 'partial':
                        # ยอดค้างรวม VAT
                        amount_residual_with_vat = move_ty.amount_residual or 0  # = 180

                        # คำนวณแยก
                        amount_residual_without_vat = amount_residual_with_vat / 1.07  # = 168.22
                        vat_amount = amount_residual_with_vat - amount_residual_without_vat  # = 11.78

                        # บวกเข้า total ที่ถูกต้อง
                        total_rental_unpaid_amount += amount_residual_without_vat  # += 168.22 (ยอดก่อน VAT)
                        total_vat_rental_unpaid_amount += vat_amount  # += 11.78 (VAT)

                account_ty_moves = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so.name),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('state', '!=', 'cancel'),  # 🔧 ไม่รวม ใบแจ้งหนี้ที่ยกเลิก
                    '|',
                    ('payment_state', '=', 'not_paid'),
                    ('payment_state', '=', 'partial'),
                    '|',  # OR สำหรับชื่อ
                    ('name', 'like', 'ILS-%'),
                    ('name', 'like', 'IBK-%')
                ])
                for move_ty in account_ty_moves:
                    reason = move_ty.reason_code_id.name or ''
                    if reason == 'สินค้าหาย' and move_ty.payment_state == 'partial':
                        total_lost_unpaid_amount += move_ty.amount_residual or 0
                    elif reason == 'สินค้าหาย' and move_ty.payment_state != 'partial':
                        total_lost_unpaid_amount += move_ty.wht_amt_net or 0

                    if reason == 'สินค้าชำรุด' and move_ty.payment_state == 'partial':
                        total_damaged_unpaid_amount += move_ty.amount_residual or 0
                    elif reason == 'สินค้าชำรุด' and move_ty.payment_state != 'partial':
                        total_damaged_unpaid_amount += move_ty.wht_amt_net or 0

            # account_rental_moves = self.env['account.move'].sudo().search([
            #     # ('invoice_origin', '=', so.name),
            #     ('invoice_date', '=', ''),
            #     ('payment_state', '=', 'paid'),
            #     ('name', 'like', 'INV-%'),
            # ])

            # date_domain = []
            # if self.date_from:
            #     date_domain.append(('invoice_date', '>=', self.date_from))
            # if self.date_to:
            #     date_domain.append(('invoice_date', '<=', self.date_to))
            #
            # # เพิ่มเงื่อนไข branch_id
            # if self.branch_ids:
            #     date_domain.append(('branch_id', 'in', self.branch_ids.ids))
            #
            # # ถ้ามี contact_type ให้หา SO ที่ตรงเงื่อนไขก่อน
            # if self.contact_type:
            #     # หา SO ที่มี contact_type ตรงกัน
            #     so_domain = [('contact_type', '=', self.contact_type)]
            #     if self.date_from:
            #         so_domain.append(('date_order', '>=', self.date_from))
            #     if self.date_to:
            #         so_domain.append(('date_order', '<=', self.date_to + timedelta(days=1)))
            #
            #     valid_so_names = self.env['sale.order'].sudo().search(so_domain).mapped('name')
            #     date_domain.append(('invoice_origin', 'in', valid_so_names))
            #
            # account_rental_moves = self.env['account.move'].sudo().search(
            #     date_domain + [
            #         ('invoice_date', '=', report_date),
            #         ('payment_state', '=', 'paid'),
            #         ('name', 'like', 'INV-%'),
            #     ]
            # )
            #
            # for move_l in account_rental_moves:
            #     if move_l.reason_code_id.name == 'ใบแจ้งหนี้ค่าเช่า' or move_l.reason_code_id.name == 'ค่าเช่าส่วนต่าง':
            #         print("สถานะ", move_l.payment_state)
            #         print("so", move_l.name)
            #         print("ราคา", move_l.amount_total)
            #         print("=====================================")
            #
            #         total_all += move_l.amount_total_signed or 0

            # แสดงสรุป
            # print(f"\nจำนวนรายการทั้งหมด: {count_all}")
            # print(f"ยอดรวมทั้งหมด: {total_all:,.2f}")
            # total_net_rental_fee = total_all

            total_net_rental_fee = (
                                               total_rent_s + total_difference - total_rental_discount) + total_rental_payment_amount - total_rental_unpaid_amount

            # 🔧 เพิ่ม payment ที่ deferred มาสำหรับ report_date นี้
            print(f"📋 Deferred Payments Dict: {deferred_payments}")
            print(f"🔍 Current Report Date (str): {str(report_date)}")

            # if str(report_date) in deferred_payments:
            #     deferred = deferred_payments[str(report_date)]
            #     total_rental_payment_amount += deferred['rental']
            #     total_vat_rental_payment_amount += deferred['vat']
            #     total_lost_payment_amount += deferred['lost']
            #     total_damaged_payment_amount += deferred['damaged']
            if str(report_date) in deferred_payments:
                deferred = deferred_payments[str(report_date)]
                total_rental_payment_amount += deferred.get('rental', 0)
                total_vat_rental_payment_amount += deferred.get('vat', 0)
                total_lost_payment_amount += deferred.get('lost', 0)
                total_damaged_payment_amount += deferred.get('damaged', 0)

                print(
                    f"✅ Added deferred payments for {report_date}: rental={deferred['rental']:,.2f}, lost={deferred['lost']:,.2f}, damaged={deferred['damaged']:,.2f}\n")
            else:
                print(f"ℹ️  No deferred payments for {report_date}\n")

            # เก็บข้อมูลสำหรับสร้าง
            records_to_create.append({
                'report_date': report_date,
                'rental_amount': total_rent_s,
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

        # สร้างข้อมูลทั้งหมด
        if records_to_create:
            self.env['monthly.penalty.report'].sudo().create(records_to_create)

        # 🔧 เพิ่ม records สำหรับ deferred payments ที่ยังไม่ได้สร้าง
        for deferred_date, deferred_data in deferred_payments.items():
            # ตรวจสอบว่า record สำหรับวันนี้มีอยู่หรือไม่
            existing_record = [r for r in records_to_create if str(r['report_date']) == deferred_date]

            if not existing_record:
                # ถ้าไม่มี record → สร้างใหม่สำหรับ deferred payment เท่านั้น
                print(
                    f"💾 Creating deferred record for {deferred_date}: rental={deferred_data['rental']:,.2f}, lost={deferred_data['lost']:,.2f}, damaged={deferred_data['damaged']:,.2f}")
                self.env['monthly.penalty.report'].sudo().create({
                    'report_date': deferred_date,
                    'rental_amount': 0,
                    'vat': 0,
                    'insurance': 0,
                    'lost_penalty': 0,
                    'damage_penalty': 0,
                    'rental_discount': 0,
                    'line_discount': 0,
                    'net_rental_fee': deferred_data['rental'],
                    'rental_payment_amount': deferred_data['rental'],
                    'vat_rental_payment_amount': deferred_data['vat'],
                    'lost_payment_amount': deferred_data['lost'],
                    'damaged_payment_amount': deferred_data['damaged'],
                    'rental_unpaid_amount': 0,
                    'vat_rental_unpaid_amount': 0,
                    'lost_unpaid_amount': 0,
                    'damaged_unpaid_amount': 0,
                    'difference': 0,
                })
            else:
                # ถ้ามี record แล้ว → update เพิ่มเติม
                print(
                    f"📝 Updating existing record for {deferred_date}: +rental={deferred_data['rental']:,.2f}, +lost={deferred_data['lost']:,.2f}, +damaged={deferred_data['damaged']:,.2f}")

        # ✅ แก้ไข: เปิดหน้า Tree View พร้อมแสดงจำนวนสาขา
        branch_count = len(set([so.branch_id.name for so in sale_orders if so.branch_id]))
        action = {
            'type': 'ir.actions.act_window',
            'name': f'สรุปรายงานประจำเดือน - พบ {len(records_to_create)} วัน จาก {branch_count} สาขา',
            'res_model': 'monthly.penalty.report',
            'view_mode': 'tree,pivot,graph',
            'target': 'current',
        }

        try:
            tree_view = self.env.ref('stock_report_dashboard.view_tree_monthly_penalty_report', False)
            if tree_view:
                action['views'] = [
                    (tree_view.id, 'tree'),
                    (False, 'pivot'),
                    (False, 'graph'),
                ]
        except:
            pass

        return action