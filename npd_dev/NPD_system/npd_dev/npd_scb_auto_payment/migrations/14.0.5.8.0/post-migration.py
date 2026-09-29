# -*- coding: utf-8 -*-
u"""ให้ใบที่ตัดสินด้วยกติกาเก่าถูกตรวจใหม่ด้วยกติกา 3 กลุ่ม (14.0.5.8.0)

1. สลิปจ่ายบิลที่เคยขึ้น "ไม่ต้องตรวจสอบ" (ยังไม่มีรายการรายคน) -> ตรวจใหม่
   กติกาใหม่จะให้เป็น "รอข้อมูลจากธนาคาร" หรือจับคู่ได้เลยถ้ารายงานมาแล้ว
2. ใบ "ไม่สำเร็จ" ทั้งหมด -> ตรวจใหม่ 1 รอบ เพื่อแยกว่าเป็นเพราะธนาคารส่งข้อมูล
   ไม่ครบ / แนบสลิปผิด / ยอด-ชื่อไม่ตรงจริง
   ตั้งตัวนับไว้ที่ 2 -> ถ้ายังไม่สำเร็จจะครบเพดาน 3 แล้วหยุด ไม่เรียก AI ซ้ำไม่รู้จบ

ไม่อ่านสลิปใหม่ (ใช้ค่าที่ AI อ่านไว้แล้ว) ไม่แตะใบรับชำระ/รายการบัญชี
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Payment = env['account.payment']
    base = [('payment_type', '=', 'inbound'), ('partner_type', '=', 'customer'),
            ('state', '=', 'posted')]
    bill = Payment.search(base + [('scb_verify_state', '=', 'skipped'),
                                  ('scb_verify_reason', 'ilike', '"จ่ายบิล"')])
    failed = Payment.search(base + [('scb_verify_state', '=', 'failed')])
    if bill:
        bill.write({'scb_verify_state': 'to_check', 'scb_verify_attempts': 0,
                    'scb_issue_type': False,
                    'scb_verify_summary': Payment._scb_public_summary('to_check')})
    if failed:
        failed.write({'scb_verify_state': 'to_check', 'scb_verify_attempts': 2,
                      'scb_issue_type': False,
                      'scb_verify_summary': Payment._scb_public_summary('to_check')})
    _logger.info("npd_scb_auto_payment 14.0.5.8.0: ตั้งให้ตรวจใหม่ — สลิปจ่ายบิล %s ใบ, "
                 "ใบไม่สำเร็จ %s ใบ", len(bill), len(failed))
