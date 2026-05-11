# File: my_custom_module/models/sale_order_rental_status.py
from odoo import fields, models, api, exceptions
from datetime import timedelta
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class SaleOrderRentalStatus(models.Model):
    _inherit = 'sale.order'
    _description = 'Custom logic for rental status updates'

    @api.model
    def run_rental_status_update(self):
        """
        ฟังก์ชันสำหรับเรียกจาก Scheduled Action เพื่ออัปเดตสถานะการเช่า
        """
        _logger.info("=" * 70)
        _logger.info("Starting scheduled action to update rental status for Sale Orders.")

        today = fields.Date.today()

        # ค้นหาเฉพาะรายการที่มีเงื่อนไขตามที่กำหนด
        records = self.search([
            ('state', 'not in', ('draft', 'sent', 'cancel')),
            ('pfb_so_type', '=', 'rent'),
            ('name', 'like', 'SO%'),
            ('rental_status', '!=', 'done')
        ])

        _logger.info(f"Found {len(records)} records to process")

        for record in records:
            try:
                # ข้าม record ที่ rental_status = 'returned'
                if record.rental_status == 'returned':
                    continue

                _logger.info(f"Processing: {record.name}")

                # คำนวณวันที่
                rent_days = record.pfb_date_of_rent or 0
                remaining_days = 0
                overdue_days = 0

                if record.end_rent_date:
                    try:
                        end_date = fields.Date.from_string(record.end_rent_date)
                        remaining_days = max((end_date - today).days, 0)
                        overdue_days = max((today - end_date).days, 0) if today > end_date else 0
                    except Exception as e:
                        _logger.error(f"Error parsing end_rent_date for {record.name}: {e}")
                        continue

                # เก็บค่าที่จะอัปเดต
                values_to_update = {}

                # อัปเดตวันคงเหลือและวันเกิน
                if overdue_days <= 300:
                    values_to_update['rent_days_remaining'] = f"{rent_days}/{remaining_days}"
                    values_to_update['rent_days_overdue'] = overdue_days

                _logger.info(
                    f"  Remaining: {remaining_days}, Overdue: {overdue_days}, Current status: {record.rental_status}")

                # คำนวณ rental_status ใหม่ (ตรวจสอบว่า invoice paid หรือไม่)
                if record.invoice_ids and all(inv.payment_state == 'paid' for inv in record.invoice_ids):
                    _logger.info(f"  All invoices paid")

                    pricelist_name = record.pricelist_id.name if record.pricelist_id else ''
                    new_status = None

                    # *** เช็คตามลำดับความสำคัญ: overdue > due_date > nearly_due > in_rent ***

                    if overdue_days > 0:
                        # เกินกำหนดแล้ว (สำคัญที่สุด)
                        new_status = 'overdue'
                        _logger.info(f"  → Setting to OVERDUE (overdue_days={overdue_days})")

                    elif remaining_days == 0:
                        # ถึงกำหนดพอดีวันนี้
                        new_status = 'due_date'
                        _logger.info(f"  → Setting to DUE_DATE (remaining=0)")

                    elif pricelist_name == 'เรทวัน':
                        # เรทวัน: ใกล้ครบ 1 วัน
                        if remaining_days == 1:
                            new_status = 'nearly_due'
                            _logger.info(f"  → Setting to NEARLY_DUE (day rate, remaining=1)")
                        else:
                            new_status = 'in_rent'
                            _logger.info(f"  → Setting to IN_RENT (day rate)")

                    elif pricelist_name == 'เรทเดือน':
                        # เรทเดือน: ใกล้ครบ 1-3 วัน
                        if remaining_days <= 3 and remaining_days > 0:
                            new_status = 'nearly_due'
                            _logger.info(f"  → Setting to NEARLY_DUE (month rate, remaining={remaining_days})")
                        else:
                            new_status = 'in_rent'
                            _logger.info(f"  → Setting to IN_RENT (month rate)")

                    else:
                        # ไม่มี pricelist หรือไม่ตรงเงื่อนไข
                        new_status = 'in_rent'
                        _logger.info(f"  → Setting to IN_RENT (default)")

                    # เพิ่ม status ใน dict ถ้าเปลี่ยนจากเดิม
                    if new_status and new_status != record.rental_status:
                        values_to_update['rental_status'] = new_status
                        _logger.info(f"  Status change: {record.rental_status} → {new_status}")

                else:
                    _logger.info(f"  Invoices not all paid, skipping status update")

                # Update ค่าทั้งหมดครั้งเดียว
                if values_to_update:
                    _logger.info(f"  Writing: {values_to_update}")
                    record.sudo().write(values_to_update)
                    _logger.info(f"  ✓ Updated {record.name}")

            except Exception as e:
                _logger.error(f"Error processing {record.name}: {str(e)}", exc_info=True)
                continue

        _logger.info("Scheduled action finished successfully.")
        _logger.info("=" * 70)