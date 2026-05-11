from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class CancelledDocumentLog(models.Model):
    _name = 'cancelled.document.log'
    _description = 'Log of Cancelled Documents'
    _order = 'cancelled_date desc'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='ใบเช่าอ้างอิง',
        readonly=True,
        ondelete='set null',
    )
    sale_order_name = fields.Char(
        string='เลขใบเช่า',
        related='sale_order_id.name',
        store=True,
        readonly=True,
    )
    document_type = fields.Selection([
        ('sale_order', 'ใบเช่า'),
        ('invoice', 'ใบแจ้งหนี้'),
        ('delivery', 'ใบจัดส่งสินค้า'),
        ('stock_cut', 'การตัดสต๊อกสินค้า'),
        ('insurance', 'ใบรับเงินประกัน'),
        ('payment_invoice', 'ใบรับชำระใบแจ้งหนี้'),
        ('payment_insurance', 'ใบรับชำระเงินประกัน'),
        ('debit_note', 'Debit Note'),
        ('debit_note_payment', 'ใบรับชำระ Debit Note'),
        ('credit_note', 'ใบลดหนี้'),
    ], string='ประเภทเอกสาร', readonly=True)

    document_name = fields.Char(
        string='เลขเอกสารที่ยกเลิก',
        readonly=True,
    )
    reason = fields.Text(
        string='เหตุผลในการยกเลิก',
        readonly=True,
    )
    cancelled_by = fields.Many2one(
        'res.users',
        string='ผู้ยกเลิก',
        readonly=True,
    )
    cancelled_date = fields.Datetime(
        string='วันที่ยกเลิก',
        readonly=True,
    )
    branch_id = fields.Many2one(
        'res.branch',
        string='สาขาผู้ยกเลิก',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='ลูกค้า',
        related='sale_order_id.partner_id',
        store=True,
        readonly=True,
    )
    is_restored = fields.Boolean(
        string='กู้คืนแล้ว',
        default=False,
        readonly=True,
    )
    restored_by = fields.Many2one(
        'res.users',
        string='ผู้กู้คืน',
        readonly=True,
    )
    restored_date = fields.Datetime(
        string='วันที่กู้คืน',
        readonly=True,
    )

    def action_restore_to_draft(self):
        """กู้คืนเอกสารที่ยกเลิกกลับเป็นฉบับร่าง"""
        self.ensure_one()

        if self.is_restored:
            raise UserError(_('เอกสารนี้ถูกกู้คืนไปแล้ว'))

        # เช็คเงื่อนไข 3 วัน - กู้คืนได้ภายใน 3 วันหลังจากยกเลิกเท่านั้น
        if self.cancelled_date:
            cancelled_dt = self.cancelled_date
            if isinstance(cancelled_dt, str):
                cancelled_dt = fields.Datetime.from_string(cancelled_dt)
            days_since_cancel = (datetime.now() - cancelled_dt).days
            if days_since_cancel > 3:
                raise UserError(
                    _('สามารถกู้คืนเอกสารได้ภายใน 3 วันหลังจากยกเลิกเท่านั้น\n'
                      'วันที่ยกเลิก: %s (ผ่านมา %d วัน)') % (
                        cancelled_dt.strftime('%d/%m/%Y %H:%M'), days_since_cancel
                    )
                )

        doc_name = self.document_name
        doc_type = self.document_type

        # ===== ใบเช่า (Sale Order) =====
        if doc_type == 'sale_order':
            order = self.sale_order_id
            if not order:
                raise UserError(_('ไม่พบใบเช่า %s') % doc_name)
            if order.state != 'cancel':
                raise UserError(_('ใบเช่า %s ไม่ได้อยู่ในสถานะยกเลิก (สถานะปัจจุบัน: %s)') % (doc_name, order.state))

            self.env.cr.execute("""
                UPDATE sale_order SET state = 'draft' WHERE id = %s
            """, (order.id,))
            order.invalidate_cache(['state'], [order.id])
            _logger.info("[RESTORE] Sale Order %s restored to draft", doc_name)

        # ===== ใบแจ้งหนี้ / ใบรับเงินประกัน / Debit Note / ใบลดหนี้ (account.move) =====
        elif doc_type in ('invoice', 'insurance', 'debit_note', 'credit_note'):
            move = self.env['account.move'].sudo().search([
                ('name', '=', doc_name),
                ('state', '=', 'cancel'),
            ], limit=1)
            if not move:
                raise UserError(_('ไม่พบเอกสาร %s หรือเอกสารไม่ได้อยู่ในสถานะยกเลิก') % doc_name)

            move.write({'state': 'draft'})
            _logger.info("[RESTORE] %s %s restored to draft", doc_type, doc_name)

        # ===== ใบรับชำระเงิน / ใบรับชำระ Debit Note (account.payment → account.move) =====
        elif doc_type in ('payment_invoice', 'payment_insurance', 'debit_note_payment'):
            payment = self.env['account.payment'].sudo().search([
                ('name', '=', doc_name),
            ], limit=1)
            if payment and payment.move_id:
                if payment.move_id.state != 'cancel':
                    raise UserError(_('ใบรับชำระเงิน %s ไม่ได้อยู่ในสถานะยกเลิก') % doc_name)
                payment.move_id.write({'state': 'draft'})
                _logger.info("[RESTORE] Payment %s restored to draft", doc_name)
            else:
                # ลองค้นจาก account.move โดยตรง
                move = self.env['account.move'].sudo().search([
                    ('name', '=', doc_name),
                    ('state', '=', 'cancel'),
                ], limit=1)
                if not move:
                    raise UserError(_('ไม่พบใบรับชำระเงิน %s') % doc_name)
                move.write({'state': 'draft'})
                _logger.info("[RESTORE] Payment move %s restored to draft", doc_name)

        # ===== ใบจัดส่งสินค้า (stock.picking) =====
        elif doc_type == 'delivery':
            picking = self.env['stock.picking'].sudo().search([
                ('name', '=', doc_name),
                ('state', '=', 'cancel'),
            ], limit=1)
            if not picking:
                raise UserError(_('ไม่พบใบจัดส่ง %s หรือไม่ได้อยู่ในสถานะยกเลิก') % doc_name)

            # Reset picking กลับเป็น draft
            self.env.cr.execute("""
                UPDATE stock_picking SET state = 'draft' WHERE id = %s
            """, (picking.id,))
            # Reset move lines ด้วย
            self.env.cr.execute("""
                UPDATE stock_move SET state = 'draft'
                WHERE picking_id = %s AND state = 'cancel'
            """, (picking.id,))
            picking.invalidate_cache()
            _logger.info("[RESTORE] Delivery %s restored to draft", doc_name)

        # ===== การตัดสต๊อกสินค้า =====
        elif doc_type == 'stock_cut':
            raise UserError(_(
                'การตัดสต๊อกสินค้าไม่สามารถกู้คืนเป็นฉบับร่างได้\n'
                'กรุณาดำเนินการผ่านใบจัดส่งสินค้าแทน'
            ))

        else:
            raise UserError(_('ประเภทเอกสาร %s ไม่รองรับการกู้คืน') % doc_type)

        # อัปเดตสถานะ log
        self.write({
            'is_restored': True,
            'restored_by': self.env.user.id,
            'restored_date': fields.Datetime.now(),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('กู้คืนสำเร็จ'),
                'message': _('เอกสาร %s ถูกกู้คืนเป็นฉบับร่างเรียบร้อยแล้ว') % doc_name,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_restore_multi(self):
        """กู้คืนเอกสารหลายรายการพร้อมกัน (เรียกจาก Server Action)"""
        success = []
        errors = []

        for rec in self:
            try:
                if rec.is_restored:
                    errors.append('%s (กู้คืนไปแล้ว)' % rec.document_name)
                    continue
                if rec.document_type == 'stock_cut':
                    errors.append('%s (การตัดสต๊อกไม่รองรับกู้คืน)' % rec.document_name)
                    continue

                # เช็คเงื่อนไข 3 วัน
                if rec.cancelled_date:
                    cancelled_dt = rec.cancelled_date
                    if isinstance(cancelled_dt, str):
                        cancelled_dt = fields.Datetime.from_string(cancelled_dt)
                    days_since = (datetime.now() - cancelled_dt).days
                    if days_since > 3:
                        errors.append('%s (เกิน 3 วัน)' % rec.document_name)
                        continue

                rec.action_restore_to_draft()
                success.append(rec.document_name)
            except UserError as e:
                errors.append('%s (%s)' % (rec.document_name, str(e.name if hasattr(e, 'name') else e)))
            except Exception as e:
                errors.append('%s (%s)' % (rec.document_name, str(e)))

        msg_parts = []
        if success:
            msg_parts.append(_('กู้คืนสำเร็จ %d รายการ: %s') % (len(success), ', '.join(success)))
        if errors:
            msg_parts.append(_('ไม่สามารถกู้คืน %d รายการ: %s') % (len(errors), ', '.join(errors)))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('ผลการกู้คืน'),
                'message': '\n'.join(msg_parts),
                'type': 'success' if not errors else ('warning' if success else 'danger'),
                'sticky': True,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
