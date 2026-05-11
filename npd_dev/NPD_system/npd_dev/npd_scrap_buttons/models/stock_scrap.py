# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    # =======================
    # NEW FIELDS - NPD Custom
    # =======================
    # เพิ่ม state 'cancel' สำหรับยกเลิกเอกสาร
    state = fields.Selection(
        selection_add=[('cancel', 'Cancelled')],
        ondelete={'cancel': 'set default'}
    )
    
    # Field เก็บเลขเอกสารเดิม เพื่อใช้เมื่อรีเซ็ตเป็นแบบร่างแล้วกดตรวจสอบใหม่
    # จะได้ไม่รันเลขใหม่
    original_name = fields.Char(
        string='Original Reference',
        copy=False,
        readonly=True,
        help='เก็บเลขเอกสารเดิมไว้ เมื่อรีเซ็ตเป็นแบบร่างจะใช้เลขเดิม'
    )

    # =======================
    # OVERRIDE METHODS
    # =======================
    def do_scrap(self):
        """
        Override method do_scrap เพื่อเช็คว่ามีเลขเอกสารเดิมหรือไม่
        ถ้ามี original_name จะใช้เลขเดิม ไม่รัน sequence ใหม่
        """
        self._check_company()
        for scrap in self:
            # NPD Custom: เช็คว่ามีเลขเอกสารเดิมหรือไม่
            if scrap.original_name:
                # ใช้เลขเอกสารเดิม
                scrap.name = scrap.original_name
            elif scrap.name == _('New') or not scrap.name:
                # รัน sequence ใหม่เฉพาะกรณีที่ยังไม่มีเลข
                scrap.name = self.env['ir.sequence'].next_by_code('stock.scrap') or _('New')
            
            # สร้าง stock move
            move = self.env['stock.move'].create(scrap._prepare_move_values())
            move.with_context(is_scrap=True)._action_done()
            
            # อัปเดต scrap record
            scrap.write({
                'move_id': move.id,
                'state': 'done',
                'original_name': scrap.name,  # NPD Custom: เก็บเลขเอกสารไว้
            })
            scrap.date_done = fields.Datetime.now()
        return True

    # =======================
    # NEW BUTTON METHODS - NPD Custom
    # =======================
    def action_reset_to_draft(self):
        """
        รีเซ็ตเอกสาร Scrap เป็นแบบร่าง
        - สร้าง reverse stock move เพื่อโยกสินค้ากลับไปที่ location เดิม
        - เก็บเลขเอกสารเดิมไว้ใน original_name เพื่อใช้เมื่อกดตรวจสอบใหม่
        - เปลี่ยน state เป็น draft
        """
        for record in self:
            if record.state == 'done' and record.move_id:
                # สร้าง reverse move เพื่อโยกสินค้ากลับจาก scrap location ไป location เดิม
                reverse_move_vals = {
                    'name': _('Reverse: %s') % record.name,
                    'origin': record.name,
                    'company_id': record.company_id.id,
                    'product_id': record.product_id.id,
                    'product_uom': record.product_uom_id.id,
                    'state': 'draft',
                    'product_uom_qty': record.scrap_qty,
                    'location_id': record.scrap_location_id.id,      # จาก scrap location
                    'location_dest_id': record.location_id.id,       # กลับไป location เดิม
                    'move_line_ids': [(0, 0, {
                        'product_id': record.product_id.id,
                        'product_uom_id': record.product_uom_id.id,
                        'qty_done': record.scrap_qty,
                        'location_id': record.scrap_location_id.id,
                        'location_dest_id': record.location_id.id,
                        'package_id': record.package_id.id if record.package_id else False,
                        'owner_id': record.owner_id.id if record.owner_id else False,
                        'lot_id': record.lot_id.id if record.lot_id else False,
                    })],
                }
                
                # สร้างและยืนยัน reverse move
                reverse_move = self.env['stock.move'].create(reverse_move_vals)
                reverse_move._action_done()
            
            # รีเซ็ต scrap เป็น draft และเก็บเลขเอกสารเดิมไว้
            record.write({
                'state': 'draft',
                'move_id': False,
                'date_done': False,
                'original_name': record.name,  # เก็บเลขเอกสารเดิมไว้
            })
        return True

    def action_cancel(self):
        """
        ยกเลิกเอกสาร Scrap
        - สร้าง reverse stock move เพื่อโยกสินค้ากลับ (ถ้า state เป็น done)
        - เปลี่ยน state เป็น cancel
        """
        for record in self:
            if record.state == 'done' and record.move_id:
                # สร้าง reverse move เพื่อโยกสินค้ากลับ
                reverse_move_vals = {
                    'name': _('Cancel: %s') % record.name,
                    'origin': record.name,
                    'company_id': record.company_id.id,
                    'product_id': record.product_id.id,
                    'product_uom': record.product_uom_id.id,
                    'state': 'draft',
                    'product_uom_qty': record.scrap_qty,
                    'location_id': record.scrap_location_id.id,      # จาก scrap location
                    'location_dest_id': record.location_id.id,       # กลับไป location เดิม
                    'move_line_ids': [(0, 0, {
                        'product_id': record.product_id.id,
                        'product_uom_id': record.product_uom_id.id,
                        'qty_done': record.scrap_qty,
                        'location_id': record.scrap_location_id.id,
                        'location_dest_id': record.location_id.id,
                        'package_id': record.package_id.id if record.package_id else False,
                        'owner_id': record.owner_id.id if record.owner_id else False,
                        'lot_id': record.lot_id.id if record.lot_id else False,
                    })],
                }
                
                # สร้างและยืนยัน reverse move
                reverse_move = self.env['stock.move'].create(reverse_move_vals)
                reverse_move._action_done()
            
            # เปลี่ยน state เป็น cancel
            record.write({
                'state': 'cancel',
                'move_id': False,
            })
        return True
