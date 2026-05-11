# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class SaleOrderDepositStatus(models.Model):
    _inherit = 'sale.order'

    deposit_return_status = fields.Selection([
        ('not_returned', 'ลูกค้ายังไม่คืนสินค้า'),
        ('no_voucher', 'สาขายังไม่สร้างการคืนเงินประกัน'),
        ('waiting_finance', 'รอคืนเงินประกันจากการเงิน'),
        ('done', 'เสร็จสิ้น'),
    ], string='สถานะคืนเงินประกัน', readonly=True, copy=False, tracking=True)

    # =========================================================================
    # Trigger: เมื่อ sale.order.write() เปลี่ยน rental_status
    # → อัปเดต/เคลียร์ deposit_return_status ทันที
    # =========================================================================
    def write(self, vals):
        res = super(SaleOrderDepositStatus, self).write(vals)

        # trigger เมื่อ rental_status เปลี่ยน
        if 'rental_status' in vals:
            for order in self:
                try:
                    if order.pfb_so_type != 'rent':
                        continue
                    # ถ้า deposit เสร็จสิ้นแล้ว ไม่ต้องเคลียร์
                    if order.deposit_return_status == 'done':
                        continue
                    new_status = self._compute_deposit_return_status_for_order(order)
                    if new_status != order.deposit_return_status:
                        # ใช้ super().write เพื่อไม่ให้เรียก trigger วนซ้ำ
                        super(SaleOrderDepositStatus, order).write(
                            {'deposit_return_status': new_status}
                        )
                        _logger.info(
                            f"[TRIGGER-SO] {order.name}: rental_status → {vals['rental_status']}, "
                            f"deposit: {order.deposit_return_status} → {new_status}"
                        )
                except Exception as e:
                    _logger.error(
                        f"[TRIGGER-SO] Error for {order.name}: {str(e)}",
                        exc_info=True
                    )

        return res

    # =========================================================================
    # Scheduled Action (Cron) - สำรอง ทุก 15 นาที
    # =========================================================================
    @api.model
    def run_deposit_return_status_update(self):
        """
        Scheduled Action: อัปเดตสถานะการคืนเงินประกัน
        """
        _logger.info("=" * 70)
        _logger.info("[CRON] Starting deposit return status update")

        # ===== ส่วนที่ 1: อัปเดต order ที่ overdue =====
        records = self.search([
            ('rental_status', '=', 'overdue'),
            ('pfb_so_type', '=', 'rent'),
            ('name', 'like', 'SO%'),
        ])

        _logger.info(f"[CRON] Found {len(records)} overdue rental orders to check")

        for order in records:
            try:
                new_status = self._compute_deposit_return_status_for_order(order)
                if new_status != order.deposit_return_status:
                    order.sudo().write({'deposit_return_status': new_status})
                    _logger.info(
                        f"  [CRON] {order.name}: {order.deposit_return_status} -> {new_status}"
                    )
                    # เมื่อเสร็จสิ้น → อัพเดท rental_status + picking
                    if new_status == 'done':
                        self._on_deposit_done(order)
            except Exception as e:
                _logger.error(
                    f"[CRON] Error processing {order.name}: {str(e)}",
                    exc_info=True
                )
                continue

        # ===== ส่วนที่ 2: เคลียร์สถานะที่ค้าง (ไม่ใช่ overdue + ไม่ใช่ done) =====
        stale_records = self.search([
            ('rental_status', '!=', 'overdue'),
            ('deposit_return_status', '!=', False),
            ('deposit_return_status', '!=', 'done'),
            ('pfb_so_type', '=', 'rent'),
        ])

        if stale_records:
            _logger.info(f"[CRON] Clearing {len(stale_records)} stale deposit statuses")
            for order in stale_records:
                order.sudo().write({'deposit_return_status': False})
                _logger.info(
                    f"  [CRON] Cleared {order.name} "
                    f"(rental={order.rental_status}, was={order.deposit_return_status})"
                )

        _logger.info("[CRON] Deposit return status update finished")
        _logger.info("=" * 70)

    # =========================================================================
    # Core Logic - ใช้ร่วมกันทั้ง Cron และ Trigger
    # =========================================================================
    def _compute_deposit_return_status_for_order(self, order):
        """
        คำนวณสถานะการคืนเงินประกันสำหรับ order เดียว

        Logic:
        1. rental_status ต้อง = 'overdue' ก่อน ถ้าไม่ใช่ → False
        2. เช็ค stock.picking (ใช้ picking_type_id.code)
           - นับ outgoing (done) vs incoming (done)
           - ถ้า outgoing > incoming = ยังคืนไม่ครบ → 'not_returned'
        3. เช็ค account.voucher (reference = order.name)
           - ไม่พบ → 'no_voucher'
           - พบแต่ state != 'posted' → 'waiting_finance'
           - พบและ posted → False (เสร็จสิ้น)
        """
        order_name = order.name

        # ========== เงื่อนไขแรก: ต้อง overdue ==========
        if order.rental_status != 'overdue':
            return False

        # ========== ขั้นตอนที่ 1: เช็คการคืนสินค้า stock.picking ==========
        # ใช้ picking_type_id.code แทน name pattern เพื่อความแม่นยำ
        all_pickings = self.env['stock.picking'].search([
            ('group_id.name', '=', order_name),
            ('state', '=', 'done'),
        ])

        outgoing_count = len(all_pickings.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        ))
        incoming_count = len(all_pickings.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
        ))

        _logger.info(
            f"  {order_name}: outgoing={outgoing_count}, incoming={incoming_count}"
        )

        if outgoing_count > 0 and outgoing_count > incoming_count:
            # ตัดสต๊อกออกมากกว่าคืน = ยังคืนไม่ครบ
            _logger.info(f"  {order_name}: ลูกค้ายังไม่คืนสินค้า")
            return 'not_returned'

        # ========== ขั้นตอนที่ 2: เช็ค account.voucher ==========
        vouchers = self.env['account.voucher'].search([
            ('reference', '=', order_name),
        ])

        if not vouchers:
            _logger.info(f"  {order_name}: สาขายังไม่สร้างการคืนเงินประกัน")
            return 'no_voucher'

        posted_vouchers = vouchers.filtered(lambda v: v.state == 'posted')

        if not posted_vouchers:
            _logger.info(f"  {order_name}: รอคืนเงินประกันจากการเงิน")
            return 'waiting_finance'

        _logger.info(f"  {order_name}: คืนเงินประกันเสร็จสิ้น")
        return 'done'

    # =========================================================================
    # Helper: อัปเดตสถานะสำหรับ order เดียว (เรียกจาก trigger ภายนอก)
    # =========================================================================
    def _update_deposit_return_status_single(self):
        """อัปเดตสถานะคืนเงินประกันสำหรับ record ปัจจุบัน"""
        for order in self:
            try:
                new_status = self._compute_deposit_return_status_for_order(order)
                if new_status != order.deposit_return_status:
                    order.sudo().write({'deposit_return_status': new_status})
                    _logger.info(
                        f"[TRIGGER] {order.name}: {order.deposit_return_status} -> {new_status}"
                    )

                    # ===== เมื่อเสร็จสิ้น → อัพเดท rental_status + picking =====
                    if new_status == 'done':
                        self._on_deposit_done(order)

            except Exception as e:
                _logger.error(
                    f"[TRIGGER] Error updating {order.name}: {str(e)}",
                    exc_info=True
                )

    def _on_deposit_done(self, order):
        """
        เมื่อ deposit_return_status = done (เสร็จสิ้นทุกอย่าง):
        1. อัพเดท rental_status → 'done' (ปิดบิล) ผ่าน SQL ตรง
           เพราะ rental_status เป็น computed stored field → write() ปกติจะถูก recompute ทับ
        2. อัพเดท stock.picking (incoming ล่าสุด) → deposit_return_state = 'returned'
        """
        order_name = order.name

        # ===== 1. อัพเดท rental_status = done ผ่าน SQL ตรง =====
        # ต้องใช้ SQL เพราะ rental_status เป็น compute + store=True
        # ถ้าใช้ write() ปกติ Odoo จะ recompute จาก _compute_rental_status
        # แล้วเขียนทับกลับเป็น 'overdue' ตามวันที่
        if order.rental_status != 'done':
            self.env.cr.execute(
                "UPDATE sale_order SET rental_status = %s WHERE id = %s",
                ('done', order.id)
            )
            order.invalidate_cache(['rental_status'], [order.id])
            _logger.info(f"  [DONE] {order_name}: rental_status → done (via SQL)")

        # ===== 2. อัพเดท picking incoming ล่าสุด → returned =====
        last_incoming = self.env['stock.picking'].search([
            ('group_id.name', '=', order_name),
            ('picking_type_id.code', '=', 'incoming'),
            ('state', '=', 'done'),
        ], order='date_done desc', limit=1)

        if last_incoming and last_incoming.deposit_return_state != 'returned':
            last_incoming.sudo().write({'deposit_return_state': 'returned'})
            _logger.info(
                f"  [DONE] {order_name}: picking {last_incoming.name} "
                f"→ deposit_return_state = returned"
            )


class StockPickingDepositTrigger(models.Model):
    """
    Trigger: เมื่อ stock.picking ถูก validate (คืนสินค้า)
    → อัปเดตสถานะคืนเงินประกันใน sale.order ทันที
    """
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override: หลังจาก validate picking แล้ว trigger อัปเดตสถานะ"""
        res = super(StockPickingDepositTrigger, self).button_validate()

        for picking in self:
            try:
                if picking.group_id and picking.group_id.name:
                    sale_order = self.env['sale.order'].search([
                        ('name', '=', picking.group_id.name),
                        ('rental_status', '=', 'overdue'),
                        ('pfb_so_type', '=', 'rent'),
                    ], limit=1)

                    if sale_order:
                        _logger.info(
                            f"[TRIGGER-PICKING] {picking.name} validated "
                            f"→ updating {sale_order.name}"
                        )
                        sale_order._update_deposit_return_status_single()
            except Exception as e:
                _logger.error(
                    f"[TRIGGER-PICKING] Error: {str(e)}",
                    exc_info=True
                )

        return res


class AccountVoucherDepositTrigger(models.Model):
    """
    Trigger: เมื่อ account.voucher ถูก create / write / post
    → อัปเดตสถานะคืนเงินประกันใน sale.order ทันที
    """
    _inherit = 'account.voucher'

    def _trigger_deposit_status_update(self):
        """หา sale.order จาก reference แล้ว trigger อัปเดตสถานะ"""
        for voucher in self:
            try:
                if voucher.reference:
                    sale_order = self.env['sale.order'].search([
                        ('name', '=', voucher.reference),
                        ('pfb_so_type', '=', 'rent'),
                    ], limit=1)

                    if sale_order:
                        _logger.info(
                            f"[TRIGGER-VOUCHER] {voucher.number or 'draft'} "
                            f"(ref: {voucher.reference}) "
                            f"→ updating {sale_order.name}"
                        )
                        sale_order._update_deposit_return_status_single()
            except Exception as e:
                _logger.error(
                    f"[TRIGGER-VOUCHER] Error: {str(e)}",
                    exc_info=True
                )

    @api.model
    def create(self, vals):
        """Override: หลัง create voucher → trigger อัปเดตสถานะ"""
        record = super(AccountVoucherDepositTrigger, self).create(vals)
        record._trigger_deposit_status_update()
        return record

    def write(self, vals):
        """Override: หลัง write voucher (รวมถึงเปลี่ยน state) → trigger อัปเดตสถานะ"""
        res = super(AccountVoucherDepositTrigger, self).write(vals)

        if 'state' in vals or 'reference' in vals:
            self._trigger_deposit_status_update()

        return res
