# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    # ✅ เพิ่ม field สำหรับสิทธิ์การยืนยัน/ยกเลิกเอกสารคืนเงิน
    can_confirm_refund_payment = fields.Boolean(
        string='สามารถยืนยัน/ยกเลิกเอกสารคืนเงิน',
        default=False,
        help='ถ้าเลือกไว้ ผู้ใช้จะสามารถกดปุ่มยืนยันและยกเลิกเอกสารคืนเงินได้'
    )
    
    # ✅ เพิ่ม field สำหรับสิทธิ์แก้ไขวันที่
    allow_edit_refund_date = fields.Boolean(
        string='อนุญาตให้แก้ไขวันที่ในเอกสารคืนเงิน',
        default=False,
        help='ถ้าเลือกไว้ ผู้ใช้จะสามารถแก้ไขวันที่ในเอกสารคืนเงินได้ ถ้าไม่เลือก วันที่จะถูกกำหนดอัตโนมัติเป็นวันที่ปัจจุบัน'
    )