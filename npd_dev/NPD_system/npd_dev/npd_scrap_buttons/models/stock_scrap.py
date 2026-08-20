# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context

# ===========================================================================
# SLA การซ่อม: ต้องซ่อมให้เสร็จภายในกี่นาที นับจาก 'วันที่เริ่มซ่อม'
# (repair_start_date = เวลาที่กดปุ่มแจ้งซ่อม -> เอกสารเข้าสถานะ 'อยู่ระหว่างการซ่อม')
#
#   *** ปรับเวลาที่บรรทัดนี้บรรทัดเดียว ***  (ชื่อคอลัมน์/ป้ายกำกับเปลี่ยนตามเอง)
#     ใช้งานจริง : 48 * 60   -> 48 ชั่วโมง
#     ทดสอบ      : 2         -> 2 นาที
#
#   หลังแก้ต้อง restart เซิร์ฟเวอร์ (เป็นโค้ด Python) และถ้าต้องการให้ใบที่ค้าง
#   อยู่เดิมใช้เวลาใหม่ด้วย ให้สั่ง recompute repair_deadline (ดู README ในคำตอบ)
# ===========================================================================
REPAIR_SLA_MINUTES = 48 * 60

# สถานะทั้งหมดใน workflow การซ่อม
REPAIR_FLOW_STATES = ('pending_repair', 'under_repair', 'repaired')
# ช่วงที่นาฬิกา SLA เดิน: เริ่มจับเวลาเมื่อกดแจ้งซ่อม (under_repair)
# ตอนอยู่ 'รอดำเนินการแจ้งซ่อม' ยังไม่นับ เพราะยังไม่มีวันที่เริ่มซ่อม
REPAIR_SLA_STATES = ('under_repair', 'repaired')

# คำที่ใช้ระบุคลัง "ขายตามสภาพ" (ดูจาก complete_name ของ stock.location)
# โครงสร้างที่ใช้: คลังแม่ 1 ตัว + คลังลูกรายสาขาที่ผูก branch_id
#   W2/ขายตามสภาพ
#   W2/ขายตามสภาพ/ลาดกระบัง   (branch_id = ลาดกระบัง)
# ต้องเป็น usage = 'internal' เท่านั้น ของถึงจะยังอยู่ในสต็อกให้ขายต่อได้
SOLD_AS_IS_KEYWORD = 'ขายตามสภาพ'


def repair_sla_label():
    """ป้ายกำกับเวลา SLA เช่น '48 ชม.' หรือ '2 นาที' ใช้ประกอบชื่อฟิลด์/คอลัมน์"""
    if REPAIR_SLA_MINUTES and REPAIR_SLA_MINUTES % 60 == 0:
        return '%d ชม.' % (REPAIR_SLA_MINUTES // 60)
    return '%d นาที' % REPAIR_SLA_MINUTES


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    # =======================
    # STATES
    # =======================
    state = fields.Selection(
        selection_add=[
            ('cancel', 'Cancelled'),
            ('pending_repair', 'รอดำเนินการแจ้งซ่อม'),
            ('under_repair', 'อยู่ระหว่างการซ่อม'),
            ('repaired', 'ซ่อมสำเร็จ'),
            ('sold_as_is', 'ขายตามสภาพ'),
        ],
        ondelete={
            'cancel': 'set default',
            'pending_repair': 'set default',
            'under_repair': 'set default',
            'repaired': 'set default',
            'sold_as_is': 'set default',
        }
    )

    sold_as_is_date = fields.Datetime(
        string='วันที่ตัดเป็นขายตามสภาพ', readonly=True, copy=False)

    original_name = fields.Char(
        string='Original Reference',
        copy=False,
        readonly=True,
        help='เก็บเลขเอกสารเดิมไว้ เมื่อรีเซ็ตเป็นแบบร่างจะใช้เลขเดิม'
    )

    # ===== Repair Request fields (จากปุ่มแจ้งซ่อม) =====
    damage_type = fields.Char(string='ประเภทความเสียหาย', readonly=True, copy=False)
    repair_by = fields.Selection(
        [('factory', 'โรงงาน'), ('branch', 'สาขา')],
        string='ซ่อมโดย',
        readonly=True,
        copy=False,
    )
    technician_name = fields.Char(string='ชื่อผู้ซ่อม', readonly=True, copy=False)
    repair_start_date = fields.Datetime(string='วันที่เริ่มซ่อม', readonly=True, copy=False)
    damaged_attachment_ids = fields.Many2many(
        'ir.attachment',
        'rel_scrap_damaged_attachment',
        'scrap_id',
        'attachment_id',
        string='รูปสินค้าที่ชำรุด',
        copy=False,
    )

    # ===== Repair Complete fields (จากปุ่มซ่อมสำเร็จ) =====
    spare_parts_used = fields.Text(string='อะไหล่ที่ใช้ในการซ่อม', readonly=True, copy=False)
    parts_cost = fields.Float(string='ค่าอะไหล่', readonly=True, copy=False)
    labor_cost = fields.Float(string='ค่าแรง', readonly=True, copy=False)
    repair_end_date = fields.Datetime(string='วันที่ซ่อมเสร็จสิ้น', readonly=True, copy=False)
    repaired_attachment_ids = fields.Many2many(
        'ir.attachment',
        'rel_scrap_repaired_attachment',
        'scrap_id',
        'attachment_id',
        string='รูปภาพหลังซ่อม',
        copy=False,
    )

    # ===== Stock return tracking =====
    is_stock_returned = fields.Boolean(string='คืนสต็อกแล้ว', readonly=True, copy=False)
    return_move_id = fields.Many2one(
        'stock.move',
        string='การคืนสต็อก',
        readonly=True,
        copy=False,
    )
    return_date = fields.Datetime(string='วันที่คืนสต็อก', readonly=True, copy=False)

    # ===== Computed: ระยะเวลาในการซ่อม =====
    repair_duration_display = fields.Char(
        string='ระยะเวลาในการซ่อมสินค้า',
        compute='_compute_repair_duration_display',
        store=False,
    )

    @api.depends('repair_start_date', 'repair_end_date')
    def _compute_repair_duration_display(self):
        for rec in self:
            start = rec.repair_start_date
            end = rec.repair_end_date
            if not start or not end:
                rec.repair_duration_display = ''
                continue
            delta = end - start
            total_seconds = int(delta.total_seconds())
            if total_seconds <= 0:
                rec.repair_duration_display = '0 นาที'
                continue
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            parts = []
            if days:
                parts.append('%d วัน' % days)
            if hours:
                parts.append('%d ชั่วโมง' % hours)
            if minutes and not days:
                parts.append('%d นาที' % minutes)
            if not parts:
                parts.append('น้อยกว่า 1 นาที')
            rec.repair_duration_display = ' '.join(parts)

    # =======================
    # SLA 48 ชั่วโมง
    # =======================
    repair_pending_start = fields.Datetime(
        string='เข้าคิวรอแจ้งซ่อม',
        readonly=True,
        copy=False,
        help='เวลาที่เอกสารเข้าสถานะ "รอดำเนินการแจ้งซ่อม" (ยังไม่เริ่มนับ SLA)',
    )
    repair_deadline = fields.Datetime(
        string='ครบกำหนดซ่อม (%s)' % repair_sla_label(),
        compute='_compute_repair_deadline',
        store=True,
        readonly=True,
        copy=False,
        help='วันที่เริ่มซ่อม + %s (เก็บลง DB เพื่อให้รายงานภาพรวมสต็อก เช่า ดึงไปใช้ได้)'
             % repair_sla_label(),
    )
    repair_sla_state = fields.Selection(
        [
            ('waiting', 'อยู่ในกำหนด %s' % repair_sla_label()),
            ('overdue', 'เกินกำหนด'),
            ('repaired', 'ซ่อมสำเร็จ'),
        ],
        string='สถานะภายใน %s' % repair_sla_label(),
        compute='_compute_repair_sla',
        store=False,
    )
    repair_overdue_display = fields.Char(
        string='เวลาที่เกินกำหนด',
        compute='_compute_repair_sla',
        store=False,
    )
    repair_time_left_display = fields.Char(
        string='เวลาคงเหลือ',
        compute='_compute_repair_sla',
        store=False,
    )

    @staticmethod
    def _format_sla_duration(total_seconds):
        """แปลงจำนวนวินาทีเป็นข้อความไทย เช่น '2 วัน 3 ชั่วโมง 15 นาที'"""
        total_seconds = int(total_seconds)
        if total_seconds < 3600:
            # ช่วงสั้น ๆ บอกวินาทีด้วย (สำคัญตอนตั้ง SLA เป็นหลักนาทีเพื่อทดสอบ)
            return '%d นาที %d วินาที' % (total_seconds // 60, total_seconds % 60)
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        parts = []
        if days:
            parts.append('%d วัน' % days)
        if days or hours:
            parts.append('%d ชั่วโมง' % hours)
        parts.append('%d นาที' % minutes)
        return ' '.join(parts)

    @api.depends('repair_start_date', 'state')
    def _compute_repair_deadline(self):
        """ครบกำหนด = วันที่เริ่มซ่อม + SLA

        ใบที่ยัง 'รอดำเนินการแจ้งซ่อม' จะไม่มีค่า เพราะยังไม่ได้กดแจ้งซ่อม
        (ยังไม่มี repair_start_date) นาฬิกาจึงยังไม่เริ่มเดิน
        """
        for rec in self:
            start = rec.repair_start_date if rec.state in REPAIR_SLA_STATES else False
            rec.repair_deadline = (
                start + timedelta(minutes=REPAIR_SLA_MINUTES) if start else False
            )

    @api.depends('repair_deadline', 'repair_end_date', 'state')
    def _compute_repair_sla(self):
        """สถานะ/เวลาที่เกินกำหนด ณ เวลาที่อ่านค่า

        เป็น compute แบบไม่ store เพราะขึ้นกับ 'เวลาปัจจุบัน' (ถ้า store จะต้องมี
        cron คอยไล่อัปเดตทุกเรกคอร์ด = กินทรัพยากรเซิร์ฟเวอร์)
        การนับถอยหลังแบบเรียลไทม์บนหน้าจอทำที่ฝั่ง browser ด้วย widget
        npd_repair_countdown ซึ่งไม่ยิง RPC เพิ่มเลย
        """
        now = fields.Datetime.now()
        for rec in self:
            deadline = rec.repair_deadline
            if not deadline or rec.state not in REPAIR_SLA_STATES:
                rec.repair_sla_state = False
                rec.repair_overdue_display = False
                rec.repair_time_left_display = False
                continue

            if rec.state == 'repaired':
                # ไม่มีวันที่ซ่อมเสร็จ (ข้อมูลเก่า) -> ถือว่าทันกำหนด
                ref = rec.repair_end_date or deadline
            else:
                ref = now

            over = (ref - deadline).total_seconds()
            if over > 0:
                rec.repair_sla_state = 'overdue'
                rec.repair_overdue_display = self._format_sla_duration(over)
                rec.repair_time_left_display = False
            else:
                rec.repair_sla_state = 'repaired' if rec.state == 'repaired' else 'waiting'
                rec.repair_overdue_display = False
                rec.repair_time_left_display = (
                    False if rec.state == 'repaired' else self._format_sla_duration(-over)
                )

    # =======================
    # OVERRIDE METHODS
    # =======================
    def do_scrap(self):
        """
        Override do_scrap:
        - ใช้เลขเอกสารเดิมถ้ามี original_name (ไม่รัน sequence ใหม่)
        - ถ้า reason_code มี is_damage_repair=True → state=pending_repair
          มิฉะนั้น state=done (พฤติกรรมเดิม)
        """
        self._check_company()
        for scrap in self:
            # เผื่อคลังปลายทางแตกลูกรายสาขา (เช่น ขายตามสภาพ) ให้ลงคลังของสาขาตัวเอง
            scrap._apply_branch_scrap_location()
            if scrap.original_name:
                scrap.name = scrap.original_name
            elif scrap.name == _('New') or not scrap.name:
                scrap.name = self.env['ir.sequence'].next_by_code('stock.scrap') or _('New')

            move = self.env['stock.move'].create(scrap._prepare_move_values())
            move.with_context(is_scrap=True)._action_done()

            new_state = 'done'
            if scrap.reason_code_id and scrap.reason_code_id.is_damage_repair:
                new_state = 'pending_repair'

            vals = {
                'move_id': move.id,
                'state': new_state,
                'original_name': scrap.name,
            }
            if new_state == 'pending_repair':
                # จุดตั้งต้นนับ 48 ชั่วโมง
                vals['repair_pending_start'] = fields.Datetime.now()
            scrap.write(vals)
            scrap.date_done = fields.Datetime.now()
        return True

    # =======================
    # INTERNAL HELPERS
    # =======================
    # ===== คลังปลายทางแยกรายสาขา =====
    def _branch_child_location(self, base_location):
        """หาคลังลูกของ base_location ที่ผูกกับสาขาของคลังต้นทาง

        ใช้กับคลังที่แตกลูกรายสาขา เช่น 'ขายตามสภาพ' -> 'ขายตามสภาพ/ลาดกระบัง'
        ถ้าไม่มีลูกที่ตรงสาขา ก็คืนคลังแม่ตามเดิม (พฤติกรรมเดิมไม่เปลี่ยน)

        จับคู่ด้วย scrap_branch_id ไม่ใช่ branch_id เพราะโมดูลอื่นค้นหาคลัง
        ต้นทางของสาขาด้วย branch_id แบบ limit=1 ถ้าคลังพักผูก branch_id ด้วย
        จะไปแย่งผลการค้นหาจนตัดสต๊อกผิดคลัง (ดู help ของ stock.location)
        """
        self.ensure_one()
        branch = self.location_id.branch_id
        if not base_location or not branch:
            return base_location
        child = self.env['stock.location'].search([
            ('id', 'child_of', base_location.id),
            ('id', '!=', base_location.id),
            ('scrap_branch_id', '=', branch.id),
            ('usage', '=', 'internal'),
        ], limit=1)
        return child or base_location

    def _apply_branch_scrap_location(self):
        """ปรับ scrap_location_id ให้ลงคลังลูกของสาขาตัวเอง (ถ้ามี)"""
        for rec in self:
            resolved = rec._branch_child_location(rec.scrap_location_id)
            if resolved and resolved != rec.scrap_location_id:
                rec.scrap_location_id = resolved

    def _get_sold_as_is_location(self):
        """คลัง 'ขายตามสภาพ' ของสาขาต้นทาง"""
        self.ensure_one()
        branch = self.location_id.branch_id
        domain = [
            ('usage', '=', 'internal'),
            ('complete_name', 'ilike', SOLD_AS_IS_KEYWORD),
        ]
        if branch:
            domain.append(('scrap_branch_id', '=', branch.id))
        if self.company_id:
            domain.append(('company_id', 'in', [self.company_id.id, False]))
        return self.env['stock.location'].search(domain, limit=1)

    @api.onchange('reason_code_id')
    def _onchange_reason_code_id(self):
        """ต่อยอดจาก scrap_reason_code: ชี้ปลายทางไปคลังลูกของสาขาตัวเอง"""
        res = super()._onchange_reason_code_id()
        self._apply_branch_scrap_location()
        return res

    def _create_internal_move(self, src_location, dest_location, prefix):
        """ย้ายของระหว่างคลังแบบ move เปล่า (ไม่มี picking) ดูเหตุผลใน _create_reverse_move"""
        self.ensure_one()
        move_vals = {
            'name': _('%s: %s') % (prefix, self.name),
            'origin': self.name,
            'company_id': self.company_id.id,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom_id.id,
            'state': 'draft',
            'product_uom_qty': self.scrap_qty,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'picking_id': False,
            'picking_type_id': False,
            'move_line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'product_uom_id': self.product_uom_id.id,
                'qty_done': self.scrap_qty,
                'location_id': src_location.id,
                'location_dest_id': dest_location.id,
                'package_id': self.package_id.id if self.package_id else False,
                'owner_id': self.owner_id.id if self.owner_id else False,
                'lot_id': self.lot_id.id if self.lot_id else False,
            })],
        }
        move = self.env['stock.move'].with_context(
            clean_context(self.env.context)
        ).create(move_vals)
        move._action_done()
        return move

    def _create_reverse_move(self, prefix):
        """สร้าง reverse stock move คืนสินค้าจาก scrap_location → location_id เดิม

        ต้องเป็น stock move เปล่า ๆ (ไม่มี picking) เหมือน move ของ scrap เดิม
        ไม่เช่นนั้น Odoo จะสร้างเอกสารโอนย้าย (เช่น Delivery Order/OUT) ขึ้นมาใหม่
        ทำให้ดูเหมือนเป็นการ 'ตัดสต๊อก' ซ้ำทั้งที่จริงเป็นแค่การคืนของเข้าคลัง:
        - ล้าง default_* ออกจาก context (กัน default_picking_type_id รั่วเข้ามา)
        - กำหนด picking_type_id = False เพื่อให้ _should_be_assigned() คืน False
          => move จะไม่ถูกผูกเข้ากับ/สร้าง stock.picking ใด ๆ
        """
        self.ensure_one()
        return self._create_internal_move(
            self.scrap_location_id, self.location_id, prefix)

    # =======================
    # BUTTON METHODS - reset / cancel
    # =======================
    def action_reset_to_draft(self):
        states_with_move = ('done', 'pending_repair', 'under_repair', 'sold_as_is')
        repair_states = ('pending_repair', 'under_repair', 'repaired', 'sold_as_is')
        for record in self:
            if record.state in states_with_move and record.move_id:
                record._create_reverse_move(_('Reverse'))

            vals = {
                'state': 'draft',
                'move_id': False,
                'date_done': False,
                'original_name': record.name,
            }
            # ล้างข้อมูลการซ่อมเดิมเมื่อรีเซ็ตจากสถานะใน repair workflow
            if record.state in repair_states:
                vals.update({
                    'damage_type': False,
                    'repair_by': False,
                    'technician_name': False,
                    'repair_start_date': False,
                    'repair_pending_start': False,
                    'damaged_attachment_ids': [(5, 0, 0)],
                    'spare_parts_used': False,
                    'parts_cost': 0.0,
                    'labor_cost': 0.0,
                    'repair_end_date': False,
                    'repaired_attachment_ids': [(5, 0, 0)],
                    'is_stock_returned': False,
                    'return_move_id': False,
                    'return_date': False,
                    'sold_as_is_date': False,
                })
            record.write(vals)
        return True

    def action_cancel(self):
        states_with_move = ('done', 'pending_repair', 'under_repair', 'sold_as_is')
        for record in self:
            if record.state in states_with_move and record.move_id:
                record._create_reverse_move(_('Cancel'))
            record.write({
                'state': 'cancel',
                'move_id': False,
                # หยุดนาฬิกา 48 ชม. เมื่อยกเลิกเอกสาร
                'repair_pending_start': False,
            })
        return True

    # =======================
    # BUTTON METHODS - repair workflow
    # =======================
    def action_open_repair_request_wizard(self):
        self.ensure_one()
        if self.state != 'pending_repair':
            raise UserError(_('สามารถแจ้งซ่อมได้เฉพาะเอกสารสถานะ "รอดำเนินการแจ้งซ่อม" เท่านั้น'))
        return {
            'name': _('แจ้งซ่อม'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.scrap.repair.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_scrap_id': self.id},
        }

    def action_sold_as_is(self):
        """ซ่อมไม่สำเร็จ -> ย้ายของเข้าคลัง 'ขายตามสภาพ' ของสาขาตัวเอง

        ทาง B ของ flow: ตอนรับคืนยังไม่รู้ว่าซ่อมได้ไหม พอช่างประเมินแล้วซ่อมไม่ได้
        ค่อยกดปุ่มนี้ ของจะย้ายจากคลังสินค้าชำรุด -> คลังขายตามสภาพของสาขานั้น
        (ยังเป็นคลัง internal ของจึงยังอยู่ในสต็อก เอาไปเปิดบิลขายมือสองได้)
        """
        for rec in self:
            if rec.state not in ('pending_repair', 'under_repair'):
                raise UserError(_(
                    'ตัดเป็น "ขายตามสภาพ" ได้เฉพาะเอกสารสถานะ '
                    '"รอดำเนินการแจ้งซ่อม" หรือ "อยู่ระหว่างการซ่อม" เท่านั้น'))
            dest = rec._get_sold_as_is_location()
            if not dest:
                raise UserError(_(
                    'ยังไม่ได้สร้างคลัง "%s" ของสาขา %s\n'
                    'กรุณาสร้างคลังประเภท Internal ที่ผูกสาขานี้ก่อน'
                ) % (SOLD_AS_IS_KEYWORD, rec.location_id.branch_id.name or '-'))

            if rec.scrap_location_id and dest != rec.scrap_location_id:
                rec._create_internal_move(
                    rec.scrap_location_id, dest, _('Sold as is'))

            rec.write({
                'scrap_location_id': dest.id,
                'state': 'sold_as_is',
                'sold_as_is_date': fields.Datetime.now(),
            })
        return True

    def action_open_repair_complete_wizard(self):
        self.ensure_one()
        if self.state != 'under_repair':
            raise UserError(_('สามารถบันทึกซ่อมสำเร็จได้เฉพาะเอกสารสถานะ "อยู่ระหว่างการซ่อม" เท่านั้น'))
        return {
            'name': _('ซ่อมสำเร็จ'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.scrap.repair.complete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_scrap_id': self.id},
        }
