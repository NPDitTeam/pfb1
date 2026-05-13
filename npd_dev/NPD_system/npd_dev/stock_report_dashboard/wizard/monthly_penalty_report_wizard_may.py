from odoo import models, fields, api
from datetime import datetime, timedelta


class MonthlyPenaltyReportWizard(models.TransientModel):
    _name = 'monthly.penalty.report.wizard.may'
    _description = 'Wizard สำหรับสรุปรายงานหนี้ค้างชำระ'

    month = fields.Selection([
        ('1', 'มกราคม'),
        ('2', 'กุมภาพันธ์'),
        ('3', 'มีนาคม'),
        ('4', 'เมษายน'),
        ('5', 'พฤษภาคม'),
        ('6', 'มิถุนายน'),
        ('7', 'กรกฎาคม'),
        ('8', 'สิงหาคม'),
        ('9', 'กันยายน'),
        ('10', 'ตุลาคม'),
        ('11', 'พฤศจิกายน'),
        ('12', 'ธันวาคม'),
    ], string='เลือกเดือน', required=True, default=lambda self: str(datetime.now().month))

    year = fields.Integer(
        string='เลือกปี',
        required=True,
        default=lambda self: datetime.now().year
    )

    branch_ids = fields.Many2many(
        'res.branch',
        string='สาขา',
        help='เว้นว่างเพื่อดูข้อมูลทุกสาขา'
    )

    contact_type = fields.Selection([
        ('branch', 'สาขา'),
        ('sale', 'Sale')
    ], string='ประเภท Contact', help='เว้นว่างเพื่อดูข้อมูลทุกประเภท')

    def action_generate_report_may(self):
        """สร้างรายงานแยกรายรายการ SO"""
        # ลบข้อมูลเก่าทั้งหมด
        self.env['monthly.penalty.report.may'].sudo().search([]).unlink()

        # สร้าง domain สำหรับค้นหา Sale Orders
        domain = [
            ('state', 'not in', ('draft', 'sent', 'cancel')),
            ('pfb_so_type', '=', 'rent'),
            ('name', 'like', 'SO%'),
            ('rental_status', '!=', 'ready')
        ]

        # เพิ่มเงื่อนไขเดือนและปี
        month = int(self.month)
        year = self.year

        # สร้างช่วงวันที่สำหรับเดือนที่เลือก
        date_from = datetime(year, month, 1).date()
        if month == 12:
            date_to = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            date_to = datetime(year, month + 1, 1).date() - timedelta(days=1)

        domain.append(('date_order', '>=', date_from))
        domain.append(('date_order', '<=', date_to))

        # เพิ่มเงื่อนไขสาขา
        if self.branch_ids:
            domain.append(('branch_id', 'in', self.branch_ids.ids))

        if self.contact_type:
            domain.append(('contact_type', '=', self.contact_type))

        # ค้นหา Sale Orders
        sale_orders = self.env['sale.order'].sudo().search(domain, order='name asc')

        print(f"\n{'=' * 60}")
        print(f"🔍 DEBUG: ค้นหา SO สำหรับเดือน {month}/{year}")
        print(f"📊 พบ Sale Orders: {len(sale_orders)} รายการ")
        print(f"{'=' * 60}\n")

        if not sale_orders:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'แจ้งเตือน',
                    'message': 'ไม่พบข้อมูลตามเงื่อนไขที่ระบุ',
                    'type': 'info',
                    'sticky': False,
                }
            }

        # สร้าง records แยกสำหรับแต่ละ SO
        records_to_create = []

        # ประมวลผลแต่ละ SO
        for so in sale_orders:
            so_rental_amount = so.amount_total or 0
            # so_vat = so.amount_tax or 0
            so_insure = so.pfb_amount or 0 if not so.deposit_ref else 0

            so_rental_discount = 0
            so_lost = 0
            so_damage = 0
            so_line_discount = 0
            so_difference = 0

            so_rental_payment_amount = 0
            so_vat_rental_payment_amount = 0
            so_lost_payment_amount = 0
            so_damaged_payment_amount = 0

            so_rental_unpaid_amount = 0
            so_vat_rental_unpaid_amount = 0
            so_lost_unpaid_amount = 0
            so_damaged_unpaid_amount = 0

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
                    so_rental_discount += stock.rent_discount or 0

                days_used = (1 if (stock.return_date.date() == stock.start_x_date) else (
                        stock.return_date.date() - stock.start_x_date).days)

                billed_days = 1 if stock.end_x_date == stock.start_x_date else (stock.end_x_date - stock.start_x_date).days
                rental_per_day = round((so.amount_total + so.total_rental_discount) / billed_days, 2)
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
                            so_difference += value_16
                            print(
                                f"  - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน > end_x_date → so_difference += {value_16}")
                        else:
                            so_difference += 0.00
                            print(
                                f"  - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน <= end_x_date → so_difference += 0.00")

                    elif 'เรทเดือน' in (so.pricelist_id.name or ''):
                        dd = (1 if (stock.return_date.date() == stock.start_x_date) else (
                                stock.return_date.date() - stock.start_x_date).days)
                        # print(f"  - pricelist contains เรทเดือน, dd = {dd}")

                        # ✅ ไม่มี deposit_ref และไม่ถูก SO อื่นอ้างอิง
                        if not so.deposit_ref and not is_referenced_by_other and stock.return_date.date() <= stock.end_x_date:
                            so_difference += 0.00
                            # print(f"  - ไม่ถูกอ้างอิง → so_difference += 0.00")

                        # ✅ ไม่มี deposit_ref แต่ถูก SO อื่นอ้างอิง (SO ต้นทางที่ถูกต่ออายุ)
                        elif not so.deposit_ref and not is_referenced_by_other and stock.return_date.date() > stock.end_x_date:
                            so_difference += value_16
                            # print(f"  - ถูกอ้างอิงโดย {is_referenced_by_other.name} → so_difference += {value_16}")

                        # ✅ ไม่มี deposit_ref แต่ถูก SO อื่นอ้างอิง (SO ต้นทางที่ถูกต่ออายุ)
                        elif not so.deposit_ref and is_referenced_by_other and stock.return_date.date() > stock.end_x_date:
                            so_difference += value_16
                            # print(f"  - ถูกอ้างอิงโดย {is_referenced_by_other.name} → so_difference += {value_16}")

                        # ✅ ไม่มี deposit_ref แต่ถูก SO อื่นอ้างอิง (SO ต้นทางที่ถูกต่ออายุ)
                        elif not so.deposit_ref and is_referenced_by_other:
                            so_difference += 0.00
                            # so_difference += value_16
                            # print(f"  - ถูกอ้างอิงโดย {is_referenced_by_other.name} → so_difference += {value_16}")

                        else:
                            if dd < 30:
                                so_difference += 0.00
                                # print(f"  - dd < 30 → so_difference += 0.00")
                            else:
                                so_difference += value_16
                                # print(f"  - dd >= 30 → so_difference += {value_16}")
                    else:
                        so_difference += value_16
                        # print(f"  - pricelist ≠ เรทเดือน → so_difference += {value_16}")
                else:
                    # บิลที่ต่ออายุ (มี deposit_ref)
                    deposit_ref = so.deposit_ref or ''

                    # ✅ ดึงทุก ref จาก deposit_ref (ไม่ใช่แค่ตัวสุดท้าย)
                    deposit_refs = [ref.strip() for ref in deposit_ref.split(',')] if deposit_ref else []

                    print(f"\n{'=' * 60}")
                    print(f"🔍 DEBUG: คำนวณ so_difference (Report May)")
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
                                    so_difference += value_16
                                    print(
                                        f"    - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน > end_x_date → so_difference += {value_16}")
                                else:
                                    so_difference += 0.00
                                    print(
                                        f"    - campaign = {campaign_name} (โปรส่งฟรี) วันปัจจุบัน <= end_x_date → so_difference += 0.00")

                            # end_x_date เท่ากัน
                            elif 'เรทเดือน' in (so.pricelist_id.name or ''):
                                dd = (1 if (stock.return_date.date() == stock.start_x_date) else (
                                        stock.return_date.date() - stock.start_x_date).days)
                                print(f"    - pricelist contains เรทเดือน, dd = {dd}")

                                if dd < 30:
                                    so_difference += 0.00
                                    print(f"    - dd < 30 → so_difference += 0.00")
                                else:
                                    so_difference += value_16
                                    print(f"    - dd >= 30 → so_difference += {value_16}")
                            else:
                                so_difference += value_16
                                print(f"    - pricelist ≠ เรทเดือน → so_difference += {value_16}")
                        else:
                            # มี end_x_date ที่ต่างกัน หรือ วันที่คืน > วันสิ้นสุด
                            print(f"\n  📍 SUB-CASE: มี end_x_date ที่ต่างกัน หรือ วันที่คืน > วันสิ้นสุด")
                            so_difference += value_16
                            print(f"    - so_difference += {value_16}")
                    else:
                        # ไม่พบ related_pickings → ใช้ value_16 ปกติ
                        print(f"\n  📍 SUB-CASE: ไม่พบ related_pickings")
                        so_difference += value_16
                        print(f"    - so_difference += {value_16}")

                    print(f"\n  ✅ RESULT: so_difference = {so_difference}")
                    print(f"{'=' * 60}\n")

            # for stock in stock_pickings:
            #     if stock.approval_state == 'approved':
            #         so_rental_discount += stock.rent_discount or 0
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
            #                 so_difference += 0.00
            #             else:
            #                 if dd < 30:
            #                     so_difference += 0.00
            #                 else:
            #                     so_difference += value_16
            #         else:
            #             so_difference += value_16
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
            #                         so_difference += 0.00
            #                     else:
            #                         so_difference += value_16
            #                 else:
            #                     so_difference += value_16
            #             else:
            #                 # end_x_date ไม่เท่ากัน
            #                 so_difference += value_16
            #         else:
            #             # ไม่พบ related_picking → ใช้ value_16 ปกติ
            #             so_difference += value_16

            # ประมวลผลการชำระค่าเช่า
            account_moves = self.env['account.move'].sudo().search([
                ('invoice_origin', '=', so.name),
                ('state', '=', 'posted'),
                ('name', 'like', 'INV-%'),
                ('move_type', '=', 'out_invoice')
            ])

            for move in account_moves:
                if move.payment_state in ['partial', 'paid']:
                    partial_reconciles = self.env['account.partial.reconcile'].sudo().search([
                        '|',
                        ('debit_move_id.move_id', '=', move.id),
                        ('credit_move_id.move_id', '=', move.id)
                    ], order='create_date asc')

                    debit_payments = partial_reconciles.mapped('debit_move_id.payment_id')
                    credit_payments = partial_reconciles.mapped('credit_move_id.payment_id')
                    all_payments = (debit_payments | credit_payments)

                    payment_dates_raw = all_payments.mapped('date')
                    payment_dates = [str(d) if d else None for d in payment_dates_raw]
                    invoice_date_str = str(move.invoice_date)

                    # เงื่อนไข 1: ชำระในวันเดียวกับ invoice_date
                    invoice_date_payments = [pr for pr in partial_reconciles
                                             if str(pr.debit_move_id.payment_id.date) == invoice_date_str or
                                             str(pr.credit_move_id.payment_id.date) == invoice_date_str]

                    count_invoice_date = len(invoice_date_payments)

                    if count_invoice_date == 2:
                        if invoice_date_payments:
                            latest_pr = invoice_date_payments[-1]
                            so_rental_payment_amount += latest_pr.amount

                            vat_rate = 7
                            amount_without_vat = latest_pr.amount * (100 / (100 + vat_rate))
                            vat_amount = latest_pr.amount - amount_without_vat
                            so_vat_rental_payment_amount += vat_amount

                    elif count_invoice_date >= 3:
                        if len(invoice_date_payments) >= 2:
                            for pr in invoice_date_payments[1:]:
                                so_rental_payment_amount += pr.amount

                                vat_rate = 7
                                amount_without_vat = pr.amount * (100 / (100 + vat_rate))
                                vat_amount = pr.amount - amount_without_vat
                                so_vat_rental_payment_amount += vat_amount

                    # เงื่อนไข 2: ชำระในวันต่างกับ invoice_date และอยู่ในเดือนนี้
                    for pr in partial_reconciles:
                        debit_payment_date = str(
                            pr.debit_move_id.payment_id.date) if pr.debit_move_id.payment_id else None
                        credit_payment_date = str(
                            pr.credit_move_id.payment_id.date) if pr.credit_move_id.payment_id else None

                        payment_date = debit_payment_date or credit_payment_date

                        if payment_date and payment_date != invoice_date_str and payment_date != 'False':
                            try:
                                pdate = datetime.strptime(payment_date, '%Y-%m-%d').date()
                                if date_from <= pdate <= date_to:
                                    so_rental_payment_amount += pr.amount
                                    vat_rate = 7
                                    amount_without_vat = pr.amount * (100 / (100 + vat_rate))
                                    vat_amount = pr.amount - amount_without_vat
                                    so_vat_rental_payment_amount += vat_amount
                            except:
                                pass

            # ประมวลผลการชำระค่าปรับ
            account_moves_types = self.env['account.move'].sudo().search([
                ('invoice_origin', '=', so.name),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
                '|',
                ('name', 'like', 'ILS-%'),
                ('name', 'like', 'IBK-%'),
            ])

            for move in account_moves_types:
                if move.payment_state in ['partial', 'paid']:

                    reason = move.reason_code_id.name or ''
                    if reason == 'สินค้าหาย':
                        so_lost += move.wht_amt_net or 0
                        so_line_discount += move.discount_amount_computed or 0
                    elif reason == 'สินค้าชำรุด':
                        so_damage += move.wht_amt_net or 0

                    partial_reconciles = self.env['account.partial.reconcile'].sudo().search([
                        '|',
                        ('debit_move_id.move_id', '=', move.id),
                        ('credit_move_id.move_id', '=', move.id)
                    ], order='create_date asc')

                    debit_payments = partial_reconciles.mapped('debit_move_id.payment_id')
                    credit_payments = partial_reconciles.mapped('credit_move_id.payment_id')
                    all_payments = (debit_payments | credit_payments)

                    payment_dates_raw = all_payments.mapped('date')
                    invoice_date_str = str(move.invoice_date)

                    # สินค้าหาย
                    if reason == 'สินค้าหาย':
                        invoice_date_payments = [pr for pr in partial_reconciles
                                                 if str(pr.debit_move_id.payment_id.date) == invoice_date_str or
                                                 str(pr.credit_move_id.payment_id.date) == invoice_date_str]

                        count_invoice_date = len(invoice_date_payments)

                        if count_invoice_date == 2:
                            if invoice_date_payments:
                                latest_pr = invoice_date_payments[-1]
                                so_lost_payment_amount += latest_pr.amount

                        elif count_invoice_date >= 3:
                            if len(invoice_date_payments) >= 2:
                                for pr in invoice_date_payments[1:]:
                                    so_lost_payment_amount += pr.amount

                        for pr in partial_reconciles:
                            debit_payment_date = str(
                                pr.debit_move_id.payment_id.date) if pr.debit_move_id.payment_id else None
                            credit_payment_date = str(
                                pr.credit_move_id.payment_id.date) if pr.credit_move_id.payment_id else None

                            payment_date = debit_payment_date or credit_payment_date

                            if payment_date and payment_date != invoice_date_str and payment_date != 'False':
                                try:
                                    pdate = datetime.strptime(payment_date, '%Y-%m-%d').date()
                                    if date_from <= pdate <= date_to:
                                        so_lost_payment_amount += pr.amount
                                except:
                                    pass

                    # สินค้าชำรุด
                    elif reason == 'สินค้าชำรุด':
                        invoice_date_payments = [pr for pr in partial_reconciles
                                                 if str(pr.debit_move_id.payment_id.date) == invoice_date_str or
                                                 str(pr.credit_move_id.payment_id.date) == invoice_date_str]

                        count_invoice_date = len(invoice_date_payments)

                        if count_invoice_date == 2:
                            if invoice_date_payments:
                                latest_pr = invoice_date_payments[-1]
                                so_damaged_payment_amount += latest_pr.amount

                        elif count_invoice_date >= 3:
                            if len(invoice_date_payments) >= 2:
                                for pr in invoice_date_payments[1:]:
                                    so_damaged_payment_amount += pr.amount

                        for pr in partial_reconciles:
                            debit_payment_date = str(
                                pr.debit_move_id.payment_id.date) if pr.debit_move_id.payment_id else None
                            credit_payment_date = str(
                                pr.credit_move_id.payment_id.date) if pr.credit_move_id.payment_id else None

                            payment_date = debit_payment_date or credit_payment_date

                            if payment_date and payment_date != invoice_date_str and payment_date != 'False':
                                try:
                                    pdate = datetime.strptime(payment_date, '%Y-%m-%d').date()
                                    if date_from <= pdate <= date_to:
                                        so_damaged_payment_amount += pr.amount
                                except:
                                    pass

            # ประมวลผลค้างชำระ
            account_rental_ty_moves = self.env['account.move'].sudo().search([
                ('invoice_origin', '=', so.name),
                ('state', '=', 'posted'),
                '|',
                ('payment_state', '=', 'not_paid'),
                ('payment_state', '=', 'partial'),
                ('state', '!=', 'cancel'),
            ])
            for move_ty in account_rental_ty_moves:
                if move_ty.payment_state == 'not_paid':
                    so_rental_unpaid_amount += move_ty.amount_untaxed or 0
                    so_vat_rental_unpaid_amount += sum(g[1] for g in move_ty.amount_by_group or [])
                elif move_ty.payment_state == 'partial':
                    amount_residual_with_vat = move_ty.amount_residual or 0
                    amount_residual_without_vat = amount_residual_with_vat / 1.07
                    vat_amount = amount_residual_with_vat - amount_residual_without_vat

                    so_rental_unpaid_amount += amount_residual_without_vat
                    so_vat_rental_unpaid_amount += vat_amount

            account_ty_moves = self.env['account.move'].sudo().search([
                ('invoice_origin', '=', so.name),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('state', '!=', 'cancel'),
                '|',
                ('payment_state', '=', 'not_paid'),
                ('payment_state', '=', 'partial'),
                '|',
                ('name', 'like', 'ILS-%'),
                ('name', 'like', 'IBK-%')
            ])
            for move_ty in account_ty_moves:
                reason = move_ty.reason_code_id.name or ''
                if reason == 'สินค้าหาย' and move_ty.payment_state == 'partial':
                    so_lost_unpaid_amount += move_ty.amount_residual or 0
                elif reason == 'สินค้าหาย' and move_ty.payment_state != 'partial':
                    so_lost_unpaid_amount += move_ty.wht_amt_net or 0

                if reason == 'สินค้าชำรุด' and move_ty.payment_state == 'partial':
                    so_damaged_unpaid_amount += move_ty.amount_residual or 0
                elif reason == 'สินค้าชำรุด' and move_ty.payment_state != 'partial':
                    so_damaged_unpaid_amount += move_ty.wht_amt_net or 0

            # คำนวณค่าเช่าสุทธิ
            so_net_rental_fee = (
                                            so_rental_amount + so_difference - so_rental_discount) + so_rental_payment_amount - so_rental_unpaid_amount

            # เพิ่ม record สำหรับ SO นี้
            records_to_create.append({
                'report_date': so.date_order.date(),
                'customer_code': so.partner_id.id or '',
                'customer_name': so.partner_id.name or '',
                'so_number': so.name,
                'so_names': str(so.id),
                'rental_amount': so_rental_amount,
                # 'vat': so_vat,
                'insurance': so_insure,
                'lost_penalty': so_lost,
                'damage_penalty': so_damage,
                'rental_discount': so_rental_discount,
                'line_discount': so_line_discount,
                'net_rental_fee': so_net_rental_fee,
                'rental_payment_amount': so_rental_payment_amount,
                'vat_rental_payment_amount': so_vat_rental_payment_amount,
                'lost_payment_amount': so_lost_payment_amount,
                'damaged_payment_amount': so_damaged_payment_amount,
                'rental_unpaid_amount': so_rental_unpaid_amount,
                'vat_rental_unpaid_amount': so_vat_rental_unpaid_amount,
                'lost_unpaid_amount': so_lost_unpaid_amount,
                'damaged_unpaid_amount': so_damaged_unpaid_amount,
                'difference': so_difference,
            })

        # สร้างข้อมูล
        if records_to_create:
            self.env['monthly.penalty.report.may'].sudo().create(records_to_create)
            print(f"✅ สร้าง {len(records_to_create)} records สำเร็จ")

        # แสดง Tree View
        branch_count = len(set([so.branch_id.name for so in sale_orders if so.branch_id]))
        month_names = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
                       'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
        month_name = month_names[month]

        action = {
            'type': 'ir.actions.act_window',
            'name': f'สรุปรายงานหนี้ค้างชำระ {month_name} {year} - {branch_count} สาขา ({len(sale_orders)} SO)',
            'res_model': 'monthly.penalty.report.may',
            'view_mode': 'tree,form,pivot,graph',
            'target': 'current',
        }

        try:
            tree_view = self.env.ref('stock_report_dashboard.view_tree_monthly_penalty_report_may', False)
            if tree_view:
                action['views'] = [
                    (tree_view.id, 'tree'),
                    (False, 'form'),
                    (False, 'pivot'),
                    (False, 'graph'),
                ]
        except:
            pass

        return action
