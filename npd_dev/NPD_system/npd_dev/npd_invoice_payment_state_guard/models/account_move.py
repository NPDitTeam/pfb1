# -*- coding: utf-8 -*-
"""กันสถานะการชำระเงินของใบแจ้งหนี้เพี้ยนตอนแก้วันที่

อาการ (จำลองซ้ำได้ 21 ส.ค. 2026 บน NPD_Intertrading_New)
    เปิดใบแจ้งหนี้ที่ลงบันทึกแล้วและยังค้างชำระ -> แก้ "วันที่ใบแจ้งหนี้"
    หน้าจอเด้งเป็น "ชำระเงินแล้ว" ทันทีตั้งแต่ยังไม่กดบันทึก

เหตุผล
    amount_residual กับ payment_state เป็นฟิลด์ compute แบบ store และถูกวางไว้
    บนฟอร์ม พอแก้วันที่ Odoo จะรัน onchange แล้วคำนวณสองฟิลด์นี้ใหม่บนเรคคอร์ด
    ชั่วคราวในหน่วยความจำ ซึ่งยังไม่มีข้อมูลการ reconcile ผลจึงออกมาเป็น
    "ไม่มียอดค้าง = ชำระแล้ว" เบราว์เซอร์ถือว่าสองฟิลด์นี้ถูกแก้ เลยส่งไปกับ
    คำสั่งบันทึกด้วย ค่าที่ผิดจึงถูกเขียนทับลงฐานข้อมูลจริง

    ทดสอบยืนยันแล้ว: write({'invoice_date':..., 'payment_state':'paid'})
    ทำให้ใบที่ยังค้าง 1,500 บาท กลายเป็น paid ค้างถาวรจนกว่าจะสั่งคำนวณใหม่

วิธีแก้ (ตามที่ผู้ใช้เลือก 21 ส.ค. 2026)
    ล็อกไม่ให้แก้ "วันที่ใบแจ้งหนี้" และ "Branch" ตอนใบลงบันทึกแล้ว
    ต้องรีเซ็ตเป็นฉบับร่างก่อนถึงจะแก้ได้ พอโพสต์ใหม่ Odoo จะคำนวณยอดค้าง
    กับสถานะให้ครบถ้วนเอง

    ล็อก 2 ชั้น
      1. หน้าจอ : ช่องวันที่ใบแจ้งหนี้เป็น readonly (views/account_move_views.xml)
      2. โมเดล  : กันไว้ใน write() ครอบคลุมทุกทางเข้า และใช้กับ Branch ด้วย

    และมีตัวล้างย้อนหลังสำหรับใบที่เพี้ยนไปแล้วก่อนติดตั้งโมดูล
    เรียกอัตโนมัติจาก Scheduled Action ทุกคืนตี 2
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ฟิลด์ที่ห้ามแก้เมื่อใบลงบันทึกแล้ว -> ชื่อที่จะขึ้นในข้อความเตือน
LOCKED_WHEN_POSTED = [
    ('invoice_date', 'วันที่ใบแจ้งหนี้'),
    ('branch_id', 'Branch'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # ล็อกไม่ให้แก้ฟิลด์สำคัญตอนใบลงบันทึกแล้ว
    #
    # ล็อกที่ระดับโมเดล ไม่ได้ล็อกทีละวิว เพราะช่อง Branch ถูกใส่เข้าฟอร์มมาจาก
    # คนละโมดูล และแต่ละฐานข้อมูลติดตั้งโมดูลไม่เหมือนกัน (บาง DB ใช้
    # pfb_npd_all_customs บาง DB ใช้ npd_all_customs) การไล่แก้ทีละวิวจะพังง่าย
    # วิธีนี้กันได้ทุกทางเข้า ทั้งหน้าจออื่น การนำเข้าข้อมูล และ API
    # งานเบื้องหลังที่จำเป็นต้องแก้จริง ๆ ให้ส่ง context bypass_posted_lock=True
    # ------------------------------------------------------------------
    def _posted_lock_changed_labels(self, vals):
        """ชื่อฟิลด์ที่ถูกแก้จริงบนใบที่ลงบันทึกแล้ว (ส่งค่าเดิมซ้ำมาไม่นับ)"""
        labels = []
        for fname, label in LOCKED_WHEN_POSTED:
            if fname not in vals or fname not in self._fields:
                continue
            new_value = vals[fname]
            for move in self:
                if move.state != 'posted':
                    continue
                current = move[fname]
                if self._fields[fname].type == 'many2one':
                    current = current.id
                if (current or False) != (new_value or False):
                    labels.append(label)
                    break
        return labels

    def write(self, vals):
        if self and not self.env.context.get('bypass_posted_lock'):
            changed = self._posted_lock_changed_labels(vals)
            if changed:
                raise UserError(_(
                    'ใบแจ้งหนี้ที่ลงบันทึกแล้ว แก้ไข %s ไม่ได้\n\n'
                    'ถ้าต้องการแก้ กรุณากด "รีเซ็ตเป็นแบบร่าง" ก่อน '
                    'แล้วค่อยแก้และลงบันทึกใหม่\n\n'
                    'เหตุผล: การแก้ฟิลด์เหล่านี้ตอนที่ใบลงบันทึกแล้ว ทำให้ยอดค้างชำระ'
                    'และสถานะการชำระเงินเพี้ยน ใบที่ยังค้างเงินจะกลายเป็น "ชำระเงินแล้ว"'
                ) % ' / '.join(changed))
        return super(AccountMove, self).write(vals)

    # ------------------------------------------------------------------
    # ล้างใบที่เพี้ยนไปแล้ว
    # ------------------------------------------------------------------
    @api.model
    def _wrong_payment_state_domain(self):
        """ใบที่สถานะกับยอดค้างขัดกันเอง

        1. บอกว่าชำระแล้ว แต่ยังมียอดค้าง
        2. บอกว่ายังไม่ชำระ/ชำระบางส่วน แต่ยอดค้างหมดแล้ว
        """
        return [
            '&',
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')),
            '|',
            '&', ('payment_state', '=', 'paid'), ('amount_residual', '>', 0.005),
            '&', ('payment_state', 'in', ('not_paid', 'partial')),
            ('amount_residual', '<=', 0.005),
        ]

    @api.model
    def fix_wrong_payment_state(self):
        """สั่งคำนวณยอด/สถานะใหม่ให้ใบที่ขัดกันเอง (เรียกจาก cron หรือด้วยมือ)"""
        moves = self.search(self._wrong_payment_state_domain())
        if not moves:
            return 0
        moves._compute_amount()
        _logger.info('npd_invoice_payment_state_guard: คำนวณสถานะใหม่ %s ใบ', len(moves))
        return len(moves)
