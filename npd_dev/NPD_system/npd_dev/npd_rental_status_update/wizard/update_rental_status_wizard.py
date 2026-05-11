# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# Dictionary สำหรับแปลง rental_status เป็นภาษาไทย
RENTAL_STATUS_LABELS = {
    'due_date': 'ครบกำหนด',
    'nearly_due': 'ใกล้ครบกำหนด',
    'overdue': 'เกินกำหนด',
    'in_rent': 'อยู่ระหว่างการเช่า',
    'ready': 'ทำราคา',
    'done': 'ปิดบิล',
}

class UpdateRentalStatusWizard(models.TransientModel):
    _name = 'update.rental.status.wizard'
    _description = 'Wizard สำหรับอัพเดทสถานะ rental_status'

    order_ids = fields.Many2many(
        'sale.order',
        string='รายการขาย',
    )
    
    is_admin_user = fields.Boolean(
        string='มีสิทธิ์พิเศษ',
        default=False,
    )
    
    new_status = fields.Selection([
        ('due_date', 'ครบกำหนด'),
        ('nearly_due', 'ใกล้ครบกำหนด'),
        ('overdue', 'เกินกำหนด'),
        ('in_rent', 'อยู่ระหว่างการเช่า'),
        ('ready', 'ทำราคา'),
        ('done', 'ปิดบิล'),
    ], string='สถานะใหม่', default='done')

    @api.model
    def default_get(self, fields_list):
        res = super(UpdateRentalStatusWizard, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['order_ids'] = [(6, 0, active_ids)]
        # ตรวจสอบสิทธิ์ผู้ใช้ (ใช้ sudo เพื่อให้อ่านค่าได้แน่นอน)
        user = self.env['res.users'].sudo().browse(self.env.uid)
        res['is_admin_user'] = user.allow_update_any_rental_status
        return res

    def action_update_status(self):
        """อัพเดทสถานะ rental_status ตามสิทธิ์ผู้ใช้"""
        if not self.order_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        user = self.env.user
        # ใช้ sudo เพื่อให้อ่านค่าได้แน่นอน
        user_sudo = self.env['res.users'].sudo().browse(self.env.uid)
        is_admin = user_sudo.allow_update_any_rental_status
        
        if is_admin:
            # ผู้ใช้มีสิทธิ์พิเศษ - อัพเดทเป็นสถานะที่เลือก
            new_status = self.new_status or 'done'
            new_status_label = RENTAL_STATUS_LABELS.get(new_status, new_status)
            
            for order in self.order_ids:
                old_status = RENTAL_STATUS_LABELS.get(order.rental_status, order.rental_status)
                
                _logger.info(
                    'Rental Status Update (Admin): User [%s] (ID: %s) updated Order [%s] (ID: %s) from [%s] to [%s]',
                    user.name, user.id, order.name, order.id, old_status, new_status_label
                )
                
                order.message_post(
                    body=_('<strong>อัพเดทสถานะการเช่า (สิทธิ์พิเศษ)</strong><br/>'
                           'ผู้ดำเนินการ: %s<br/>'
                           'สถานะเดิม: %s<br/>'
                           'สถานะใหม่: %s') % (user.name, old_status, new_status_label),
                    message_type='notification',
                )
                
                # Write ทีละ record เพื่อหลีกเลี่ยงปัญหา singleton
                order.write({'rental_status': new_status})
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('สำเร็จ'),
                    'message': _('อัพเดทสถานะเป็น "%s" เรียบร้อยแล้ว จำนวน %s รายการ') % (new_status_label, len(self.order_ids)),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # ผู้ใช้ทั่วไป - ตรวจสอบเงื่อนไขและอัพเดทเป็น done เท่านั้น
            allowed_statuses = ['due_date', 'overdue']
            valid_orders = self.order_ids.filtered(lambda o: o.rental_status in allowed_statuses)
            invalid_orders = self.order_ids.filtered(lambda o: o.rental_status not in allowed_statuses)
            
            if not valid_orders:
                raise UserError(_(
                    'ไม่สามารถปิดบิลได้!\n\n'
                    'ไม่มีรายการที่อยู่ในสถานะ "ครบกำหนด" หรือ "เกินกำหนด"\n\n'
                    'กรุณาเลือกเฉพาะรายการที่มีสถานะ "ครบกำหนด" หรือ "เกินกำหนด" เท่านั้น'
                ))
            
            # Log และอัพเดทเฉพาะ valid orders ทีละ record
            for order in valid_orders:
                old_status = RENTAL_STATUS_LABELS.get(order.rental_status, order.rental_status)
                
                _logger.info(
                    'Rental Status Update: User [%s] (ID: %s) updated Order [%s] (ID: %s) from [%s] to [done/ปิดบิล]',
                    user.name, user.id, order.name, order.id, old_status
                )
                
                order.message_post(
                    body=_('<strong>อัพเดทสถานะการเช่า</strong><br/>'
                           'ผู้ดำเนินการ: %s<br/>'
                           'สถานะเดิม: %s<br/>'
                           'สถานะใหม่: ปิดบิล') % (user.name, old_status),
                    message_type='notification',
                )
                
                # Write ทีละ record เพื่อหลีกเลี่ยงปัญหา singleton
                order.write({'rental_status': 'done'})
            
            # สร้างข้อความแจ้งเตือน
            message = _('อัพเดทสถานะเป็น "ปิดบิล" เรียบร้อยแล้ว จำนวน %s รายการ') % len(valid_orders)
            if invalid_orders:
                invalid_names = ', '.join(invalid_orders.mapped('name'))
                message += _('\n\nรายการที่ไม่ได้อัพเดท (สถานะไม่ถูกต้อง): %s') % invalid_names
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('สำเร็จ'),
                    'message': message,
                    'type': 'success' if not invalid_orders else 'warning',
                    'sticky': True if invalid_orders else False,
                }
            }
