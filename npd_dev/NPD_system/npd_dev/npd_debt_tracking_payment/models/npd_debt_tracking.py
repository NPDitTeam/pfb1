# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class NpdDebtTrackingPayment(models.Model):
    _inherit = 'npd.debt.tracking'

    # ฟิลด์เก็บยอดที่ชำระแล้ว จาก account.payment
    payment_amount = fields.Float(
        string='ยอดที่ชำระแล้ว',
        readonly=True,
        default=0.0,
        help='ยอดเงินที่ชำระจากใบรับชำระ'
    )
    
    # ฟิลด์อ้างอิง payment ที่ชำระ
    payment_id = fields.Many2one(
        'account.payment',
        string='ใบรับชำระ',
        readonly=True,
        help='ใบรับชำระที่เชื่อมโยง'
    )
    
    # ฟิลด์วันที่ชำระ
    payment_date = fields.Date(
        string='วันที่ชำระ',
        readonly=True,
        help='วันที่ทำการชำระเงิน'
    )
    
    # ฟิลด์ผู้ทำรายการชำระ
    payment_user_id = fields.Many2one(
        'res.users',
        string='ผู้ทำรายการชำระ',
        readonly=True,
        help='ผู้ที่กดยืนยันการชำระเงิน'
    )

    def update_payment_amount(self, payment, amount, user):
        """อัปเดตยอดชำระจาก account.payment"""
        self.write({
            'payment_amount': amount,
            'payment_id': payment.id,
            'payment_date': payment.date,
            'payment_user_id': user.id,
        })
        _logger.info(f"✅ อัปเดตยอดชำระ {amount} บาท โดย {user.name} สำหรับ Debt Tracking ID: {self.id}")

    def clear_payment_amount(self):
        """เคลียร์ยอดชำระเมื่อ payment ถูก reset to draft"""
        self.write({
            'payment_amount': 0.0,
            'payment_id': False,
            'payment_date': False,
            'payment_user_id': False,
        })
        _logger.info(f"✅ เคลียร์ยอดชำระสำหรับ Debt Tracking ID: {self.id}")
