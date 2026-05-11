# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderCampaignRestriction(models.Model):
    _inherit = 'sale.order'

    @api.constrains('campaign_id', 'contact_type', 'amount_total')
    def _check_campaign_restriction(self):
        """
        ตรวจสอบเงื่อนไขการเลือกแคมเปญ:
        
        กรณีการติดต่อของลูกค้า = "สาขา" (branch):
        - ยอดเช่า 7,500 - 30,000 → เลือกได้เฉพาะ "โปร 2026 ส่งฟรีไม่เกิน 25 Km."
        - ยอดเช่า 30,001 ขึ้นไป → เลือกได้เฉพาะ "โปร 2026 ส่งฟรีไม่เกิน 35 Km."
        
        กรณีการติดต่อของลูกค้า = "Sales" (sale):
        - ยอดเช่า 30,000 ขึ้นไป → เลือกได้เฉพาะ "โปร 2026 ส่งฟรีไม่เกิน 35 Km."
        """
        # ชื่อแคมเปญที่กำหนด
        CAMPAIGN_25KM = 'โปร 2026 ส่งฟรีไม่เกิน 25 Km.'
        CAMPAIGN_35KM = 'โปร 2026 ส่งฟรีไม่เกิน 35 Km.'
        
        for order in self:
            # ข้ามถ้าไม่ได้เลือกแคมเปญ
            if not order.campaign_id:
                continue
                
            campaign_name = order.campaign_id.name
            amount = order.amount_total
            contact_type = order.contact_type
            
            # ========== กรณีการติดต่อของลูกค้า = "สาขา" (branch) ==========
            if contact_type == 'branch':
                # เงื่อนไข 1: ยอดเช่า 7,500 - 30,000 ต้องเลือก 25 Km.
                if 7500 <= amount <= 30000:
                    if campaign_name == CAMPAIGN_35KM:
                        raise ValidationError(_(
                            'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                            'เงื่อนไข: การติดต่อลูกค้า "สาขา" + ยอดเช่า 7,500 - 30,000 บาท\n'
                            'สามารถเลือกได้เฉพาะ "%s" เท่านั้น'
                        ) % CAMPAIGN_25KM)
                
                # เงื่อนไข 2: ยอดเช่า 30,001 ขึ้นไป ต้องเลือก 35 Km.
                elif amount >= 30001:
                    if campaign_name == CAMPAIGN_25KM:
                        raise ValidationError(_(
                            'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                            'เงื่อนไข: การติดต่อลูกค้า "สาขา" + ยอดเช่า 30,001 บาทขึ้นไป\n'
                            'สามารถเลือกได้เฉพาะ "%s" เท่านั้น'
                        ) % CAMPAIGN_35KM)
                
                # เงื่อนไข 3: ยอดเช่าต่ำกว่า 7,500 ไม่สามารถใช้โปรได้
                elif amount < 7500:
                    if campaign_name in [CAMPAIGN_25KM, CAMPAIGN_35KM]:
                        raise ValidationError(_(
                            'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                            'เงื่อนไข: การติดต่อลูกค้า "สาขา" + ยอดเช่าต่ำกว่า 7,500 บาท\n'
                            'ไม่สามารถใช้โปรโมชั่นนี้ได้'
                        ))
            
            # ========== กรณีการติดต่อของลูกค้า = "Sales" (sale) ==========
            elif contact_type == 'sale':
                # เงื่อนไข: ยอดเช่า 30,000 ขึ้นไป ต้องเลือก 35 Km. เท่านั้น
                if amount >= 30000:
                    if campaign_name == CAMPAIGN_25KM:
                        raise ValidationError(_(
                            'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                            'เงื่อนไข: การติดต่อลูกค้า "Sales" + ยอดเช่า 30,000 บาทขึ้นไป\n'
                            'สามารถเลือกได้เฉพาะ "%s" เท่านั้น'
                        ) % CAMPAIGN_35KM)
                
                # ยอดเช่าต่ำกว่า 30,000 ไม่สามารถใช้โปรได้
                elif amount < 30000:
                    if campaign_name in [CAMPAIGN_25KM, CAMPAIGN_35KM]:
                        raise ValidationError(_(
                            'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                            'เงื่อนไข: การติดต่อลูกค้า "Sales" + ยอดเช่าต่ำกว่า 30,000 บาท\n'
                            'ไม่สามารถใช้โปรโมชั่นนี้ได้'
                        ))

    @api.onchange('campaign_id')
    def _onchange_campaign_warning(self):
        """
        แสดง Warning เมื่อเลือกแคมเปญที่อาจไม่เข้าเงื่อนไข
        """
        CAMPAIGN_25KM = 'โปร 2026 ส่งฟรีไม่เกิน 25 Km.'
        CAMPAIGN_35KM = 'โปร 2026 ส่งฟรีไม่เกิน 35 Km.'
        
        if not self.campaign_id:
            return
            
        campaign_name = self.campaign_id.name
        amount = self.amount_total
        contact_type = self.contact_type
        warning_msg = False
        
        # ========== กรณีการติดต่อของลูกค้า = "สาขา" (branch) ==========
        if contact_type == 'branch':
            if 7500 <= amount <= 30000:
                if campaign_name == CAMPAIGN_35KM:
                    warning_msg = (
                        'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                        'เงื่อนไข: การติดต่อลูกค้า "สาขา" + ยอดเช่า 7,500 - 30,000 บาท\n'
                        'สามารถเลือกได้เฉพาะ "%s" เท่านั้น'
                    ) % CAMPAIGN_25KM
            elif amount >= 30001:
                if campaign_name == CAMPAIGN_25KM:
                    warning_msg = (
                        'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                        'เงื่อนไข: การติดต่อลูกค้า "สาขา" + ยอดเช่า 30,001 บาทขึ้นไป\n'
                        'สามารถเลือกได้เฉพาะ "%s" เท่านั้น'
                    ) % CAMPAIGN_35KM
            elif amount < 7500:
                if campaign_name in [CAMPAIGN_25KM, CAMPAIGN_35KM]:
                    warning_msg = (
                        'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                        'เงื่อนไข: การติดต่อลูกค้า "สาขา" + ยอดเช่าต่ำกว่า 7,500 บาท\n'
                        'ไม่สามารถใช้โปรโมชั่นนี้ได้'
                    )
        
        # ========== กรณีการติดต่อของลูกค้า = "Sales" (sale) ==========
        elif contact_type == 'sale':
            if amount >= 30000:
                if campaign_name == CAMPAIGN_25KM:
                    warning_msg = (
                        'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                        'เงื่อนไข: การติดต่อลูกค้า "Sales" + ยอดเช่า 30,000 บาทขึ้นไป\n'
                        'สามารถเลือกได้เฉพาะ "%s" เท่านั้น'
                    ) % CAMPAIGN_35KM
            elif amount < 30000:
                if campaign_name in [CAMPAIGN_25KM, CAMPAIGN_35KM]:
                    warning_msg = (
                        'โปรไม่เข้าเงื่อนไขที่กำหนด กรุณาเลือกใหม่\n\n'
                        'เงื่อนไข: การติดต่อลูกค้า "Sales" + ยอดเช่าต่ำกว่า 30,000 บาท\n'
                        'ไม่สามารถใช้โปรโมชั่นนี้ได้'
                    )
        
        if warning_msg:
            return {
                'warning': {
                    'title': _('คำเตือน: โปรไม่เข้าเงื่อนไข'),
                    'message': warning_msg
                }
            }
