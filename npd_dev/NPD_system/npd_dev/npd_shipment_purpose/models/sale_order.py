# -*- coding: utf-8 -*-
"""ประเภทการจัดส่งสินค้า + หมายเหตุ (ให้ AI ตรวจ) บนใบสั่งขาย

ที่มา: ฝ่ายขนส่งต้องรู้ว่างานนี้คือ "ไปส่งของ / ไปรับของ / โยกของระหว่างสาขา /
เอารถไปช่วยสาขาอื่น" เพื่อให้ฝั่ง Odoo 18 (ข้อมูลขนส่ง + จองคิวรถ) เห็นเจตนาของงาน
ไม่ใช่เดาจากช่อง "ประเภทการจัดส่ง" เดิมที่มีแค่ 2 ค่า

หมายเหตุเรื่องใบโยกสินค้า: ใบโยก (stock.api.transfer) ถูกสร้างไว้ใน "ฐานของบริษัท
ต้นทาง" (S Group / อินเตอร์เทรดดิ้ง / กรุงเทพ ฯลฯ) ฐานโลจิสติกส์ไม่มีข้อมูลนั้น
จึงให้พนักงาน "กรอกเลขใบโยก" แล้วกดดึงข้อมูลผ่าน API เหมือนการดึงข้อมูลการเช่า
"""
import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ประเภทที่ต้องอ้างอิงเอกสารเช่า/ขายจากบริษัทอื่น
PURPOSE_NEED_SO = ('to_customer', 'from_customer')
# ประเภทที่ไม่ต้องอ้างอิงเอกสารใด ๆ (ล็อกช่องไว้)
PURPOSE_NO_REF = ('help_branch',)

PURPOSE_LABELS = {
    'to_customer': 'จัดส่งสินค้าไปยังลูกค้า',
    'from_customer': 'รับสินค้าจากลูกค้ามายังสาขา',
    'branch_transfer': 'โยกสินค้าจากสาขา ไปสาขา',
    'help_branch': 'ส่งรถไปช่วยขนส่งอีกสาขา',
}

# ประเภทการจัดส่งสินค้า -> ประเภทการจัดส่ง (ช่องเดิม) ตั้งให้อัตโนมัติและล็อกไว้
PURPOSE_TO_DELIVERY_TYPE = {
    'to_customer': 'customer',
    'from_customer': 'branch',
    'branch_transfer': 'branch_transfer',
    'help_branch': 'help_branch',
}

API_BASE_URL = 'https://npderp.com'
API_LOGIN = 'Npd_admin'
API_PASSWORD = '1234'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shipment_purpose = fields.Selection(
        selection=[
            ('to_customer', 'จัดส่งสินค้าไปยังลูกค้า'),
            ('from_customer', 'รับสินค้าจากลูกค้ามายังสาขา'),
            ('branch_transfer', 'โยกสินค้าจากสาขา ไปสาขา'),
            ('help_branch', 'ส่งรถไปช่วยขนส่งอีกสาขา'),
        ],
        string='ประเภทการจัดส่งสินค้า',
        # ไม่มีค่าเริ่มต้น — ต้องเลือกเองทุกใบ (บังคับผ่านวิว + ตรวจตอนยืนยันใบ)
        tracking=True,
        copy=False,
    )

    # ประเภทการจัดส่ง (ของเดิม customer/branch) เพิ่ม 2 ค่าให้ตรงกับประเภทการจัดส่งสินค้า
    delivery_type = fields.Selection(
        selection_add=[
            ('branch_transfer', 'โยกสินค้าจากสาขา ไปสาขา'),
            ('help_branch', 'ส่งรถไปช่วยขนส่งอีกสาขา'),
        ],
        ondelete={'branch_transfer': 'set default', 'help_branch': 'set default'},
    )

    # ---------------- ใบโยกสินค้า (ใช้แทนเลขเอกสาร SO เมื่อเป็นงานโยกระหว่างสาขา) ----------
    # เป็นช่อง "กรอกเอง" ไม่ใช่ dropdown เพราะใบโยกอยู่ในฐานของบริษัทต้นทาง
    transfer_ref = fields.Char(
        string='เลขโยกสินค้า',
        copy=False,
        index=True,
        help='กรอกเลขใบโยกสินค้าที่สถานะ "ยืนยันแล้ว" ของฐานที่เลือกไว้ '
             'แล้วกดปุ่ม "ดึงข้อมูลใบโยก" — เลขเดิมใช้ซ้ำกับใบสั่งขายอื่นไม่ได้',
    )
    transfer_product_summary = fields.Text(
        string='สินค้าที่โยก', copy=False, readonly=True,
    )

    # ---------------- หมายเหตุ + ผลตรวจของ AI ----------------
    shipment_note = fields.Text(
        string='หมายเหตุ', copy=False,
        help='อธิบายงานขนส่งครั้งนี้ให้สอดคล้องกับประเภทการจัดส่งสินค้าที่เลือก',
    )
    shipment_note_ai_state = fields.Selection([
        ('pending', 'ยังไม่ผ่านการตรวจ'),
        ('ok', 'AI ตรวจแล้ว ตรงกัน'),
        ('skipped', 'ข้ามการตรวจ (AI ไม่พร้อมใช้งาน)'),
    ], string='ผลตรวจหมายเหตุ', readonly=True, copy=False)
    shipment_note_ai_feedback = fields.Text(
        string='ความเห็นของ AI', readonly=True, copy=False,
    )

    # ------------------------------------------------------------------
    # ตั้งค่าอัตโนมัติตามประเภทการจัดส่งสินค้า
    # ------------------------------------------------------------------
    @api.onchange('shipment_purpose')
    def _onchange_shipment_purpose(self):
        for order in self:
            purpose = order.shipment_purpose
            if not purpose:
                continue
            # ประเภทการจัดส่ง (ช่องเดิม) เดินตามประเภทการจัดส่งสินค้าเสมอ
            order.delivery_type = PURPOSE_TO_DELIVERY_TYPE.get(purpose, order.delivery_type)
            if purpose in PURPOSE_NO_REF:
                # ส่งรถไปช่วยอีกสาขา: ไม่ต้องอ้างเอกสารใด ๆ
                order.database_selection = False
                order.so_number = False
                order.transfer_ref = False
                order.transfer_product_summary = False
            elif purpose == 'branch_transfer':
                # โยกระหว่างสาขา: ใช้เลขใบโยกแทนเลขเอกสาร SO (ช่อง SO ถูกซ่อนไว้)
                order.so_number = (order.transfer_ref or '').strip() or False
            else:
                order.transfer_ref = False
                order.transfer_product_summary = False

    @api.onchange('transfer_ref')
    def _onchange_transfer_ref(self):
        """กรอกเลขใบโยกแล้ว ให้เลขเอกสาร SO (ที่ซ่อนไว้) เป็นเลขเดียวกัน"""
        for order in self:
            if order.shipment_purpose == 'branch_transfer':
                order.so_number = (order.transfer_ref or '').strip() or False

    def _sync_shipment_purpose_fields(self, vals):
        """บังคับความสัมพันธ์ฝั่งเซิร์ฟเวอร์ด้วย (กันการเขียนผ่าน import/API)"""
        # กรอก/เปลี่ยนเลขใบโยก -> เลขเอกสาร SO (ที่ซ่อนไว้) เดินตามเลขใบโยกเสมอ
        if 'transfer_ref' in vals:
            purposes = set(self.mapped('shipment_purpose')) | {vals.get('shipment_purpose')}
            if 'branch_transfer' in purposes:
                vals = dict(vals)
                vals['so_number'] = (vals.get('transfer_ref') or '').strip() or False

        purpose = vals.get('shipment_purpose')
        if not purpose:
            return vals
        vals = dict(vals)
        vals['delivery_type'] = PURPOSE_TO_DELIVERY_TYPE.get(purpose, vals.get('delivery_type'))
        if purpose in PURPOSE_NO_REF:
            vals.update({'database_selection': False, 'so_number': False, 'transfer_ref': False})
        return vals

    # ------------------------------------------------------------------
    # ดึงข้อมูลใบโยกสินค้าจากฐานของบริษัทต้นทาง
    # ------------------------------------------------------------------
    def _call_source_db_api(self, path, params):
        """ล็อกอินเข้าฐานที่เลือกแล้วยิง API (รูปแบบเดียวกับ action_fetch_rental_data)"""
        self.ensure_one()
        session = requests.Session()
        session.headers.update({'Content-Type': 'application/json'})
        login = session.post(
            '%s/web/session/authenticate' % API_BASE_URL,
            json={'jsonrpc': '2.0', 'method': 'call', 'params': {
                'db': self.database_selection, 'login': API_LOGIN, 'password': API_PASSWORD}},
            timeout=10)
        login.raise_for_status()
        if not session.cookies.get('session_id'):
            raise UserError(_('❌ เข้าสู่ระบบฐาน %s ไม่สำเร็จ') % self.database_selection)

        response = session.post(
            '%s%s' % (API_BASE_URL, path),
            json={'jsonrpc': '2.0', 'method': 'call', 'params': params},
            timeout=20)
        if response.status_code != 200:
            raise UserError(_('เกิดข้อผิดพลาดจาก API: %s') % response.text)
        data = response.json()
        if 'error' in data:
            raise UserError(_('❌ API Error: %s') % data['error'])
        result = data.get('result', {}) or {}
        if result.get('status') != 200:
            raise UserError(_('❌ %s') % (result.get('error') or 'เรียก API ไม่สำเร็จ'))
        return result.get('result', {}) or {}

    def action_fetch_transfer_data(self):
        """ปุ่ม "ดึงข้อมูลใบโยก" — เอาสินค้าในใบโยกจากฐานต้นทางมาใส่เป็นรายการสินค้า"""
        self.ensure_one()
        if self.shipment_purpose != 'branch_transfer':
            raise UserError(_('ปุ่มนี้ใช้กับประเภท "โยกสินค้าจากสาขา ไปสาขา" เท่านั้น'))
        if not self.database_selection:
            raise UserError(_('กรุณาเลือก "ดึงข้อมูลการเช่าจาก บ.อื่น" ก่อน '
                              'เพราะใบโยกสินค้าอยู่ในฐานข้อมูลนั้น'))
        ref = (self.transfer_ref or '').strip()
        if not ref:
            raise UserError(_('กรุณากรอก "เลขโยกสินค้า" ก่อน'))

        data = self._call_source_db_api('/api/get_stock_transfer', {
            'transfer_name': ref,
            'database_selection': self.database_selection,
        })
        lines = data.get('lines') or []
        if not lines:
            raise UserError(_('❌ ใบโยกสินค้า %s ไม่มีรายการสินค้า') % ref)

        if self.order_line:
            self.order_line.unlink()

        summary = []
        missing = []
        for item in lines:
            qty = item.get('request_qty') or 0
            code = (item.get('default_code') or '').strip()
            name = (item.get('product_name') or '').strip()
            product = self.env['product.product'].search([('default_code', '=', code)], limit=1) if code else False
            if not product:
                product = self.env['product.product'].search([('name', '=', name)], limit=1)
            if not product:
                missing.append('%s (%s)' % (name or '-', code or 'ไม่มีรหัส'))
                continue
            self.env['sale.order.line'].create({
                'order_id': self.id,
                'product_id': product.id,
                'name': product.name,
                'pfb_quantity': int(qty or 0),
            })
            summary.append('• %s  จำนวนขอตัด %s' % (name or product.name, qty))

        if missing:
            raise UserError(_('❌ ไม่พบสินค้าเหล่านี้ในฐานโลจิสติกส์:\n• %s') % '\n• '.join(missing))

        self.write({
            'so_number': ref,
            'transfer_product_summary': '\n'.join(summary),
        })
        _logger.info('📦 ดึงใบโยก %s จากฐาน %s ได้ %s รายการ', ref, self.database_selection, len(summary))
        return True

    # ------------------------------------------------------------------
    # กฎความครบถ้วน
    # ------------------------------------------------------------------
    @api.constrains('shipment_purpose', 'database_selection', 'so_number', 'transfer_ref')
    def _check_shipment_purpose_refs(self):
        for order in self:
            purpose = order.shipment_purpose
            if not purpose:
                continue
            if purpose in PURPOSE_NEED_SO:
                missing = []
                if not order.database_selection:
                    missing.append('ดึงข้อมูลการเช่าจาก บ.อื่น')
                if not order.so_number:
                    missing.append('เลขเอกสาร SO')
                if missing:
                    raise ValidationError(_(
                        'ประเภทการจัดส่งสินค้า "%s" ต้องระบุ: %s'
                    ) % (PURPOSE_LABELS[purpose], ' และ '.join(missing)))
            elif purpose == 'branch_transfer':
                if not order.database_selection:
                    raise ValidationError(_(
                        'ประเภทการจัดส่งสินค้า "%s" ต้องเลือก "ดึงข้อมูลการเช่าจาก บ.อื่น" ก่อน '
                        'เพราะเลขใบโยกสินค้าอยู่ในฐานข้อมูลนั้น'
                    ) % PURPOSE_LABELS[purpose])
                if not (order.transfer_ref or '').strip():
                    raise ValidationError(_(
                        'ประเภทการจัดส่งสินค้า "%s" ต้องกรอกเลขโยกสินค้า '
                        '(ใบที่สถานะ "ยืนยันแล้ว")'
                    ) % PURPOSE_LABELS[purpose])

    @api.constrains('transfer_ref')
    def _check_transfer_ref_unique(self):
        """เลขโยกสินค้าหนึ่งเลข ใช้ได้กับใบสั่งขายเดียวเท่านั้น"""
        for order in self:
            ref = (order.transfer_ref or '').strip()
            if not ref:
                continue
            other = self.sudo().search([
                ('id', '!=', order.id),
                ('transfer_ref', '=ilike', ref),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    'เลขโยกสินค้า %s ถูกใช้ไปแล้วในใบสั่งขาย %s'
                ) % (ref, other.name))

    def action_confirm(self):
        """ยืนยันใบสั่งขายไม่ได้ถ้ายังไม่ระบุประเภทการจัดส่งสินค้า/หมายเหตุ"""
        for order in self:
            if not order.shipment_purpose:
                raise ValidationError(_('กรุณาเลือก "ประเภทการจัดส่งสินค้า" ก่อนยืนยันใบสั่งขาย'))
            if not (order.shipment_note or '').strip():
                raise ValidationError(_('กรุณากรอก "หมายเหตุ" ให้สอดคล้องกับประเภทการจัดส่งสินค้า'))
        return super().action_confirm()

    # ------------------------------------------------------------------
    # create / write — ตั้งค่าอัตโนมัติ + ให้ AI ตรวจหมายเหตุ
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sync_shipment_purpose_fields(vals) for vals in vals_list]
        orders = super().create(vals_list)
        orders._run_shipment_note_ai_check()
        return orders

    def write(self, vals):
        vals = self._sync_shipment_purpose_fields(vals)
        res = super().write(vals)
        if 'shipment_note' in vals or 'shipment_purpose' in vals:
            self._run_shipment_note_ai_check()
        return res

    def _run_shipment_note_ai_check(self):
        """ให้ AI อ่านหมายเหตุเทียบกับประเภทการจัดส่งสินค้า — ไม่ตรง/คลุมเครือ = บันทึกไม่ผ่าน

        ถ้า AI ใช้งานไม่ได้ (ไม่มี key / เน็ตล่ม / ตอบไม่เป็น JSON) จะ "ไม่บล็อก"
        เพราะงานขนส่งต้องเดินต่อได้ แต่จะบันทึกสถานะไว้ว่าข้ามการตรวจ
        """
        gemini = self.env['npd.ai.it.gemini']
        for order in self:
            purpose = order.shipment_purpose
            note = (order.shipment_note or '').strip()
            if not purpose or not note:
                continue
            if not gemini.is_available():
                order._write_ai_result('skipped', 'ยังไม่ได้ตั้งค่า Gemini API key จึงข้ามการตรวจ')
                continue

            result = gemini.extract_json(order._build_note_ai_prompt(purpose, note), max_output_tokens=512)
            if not result or 'match' not in result:
                order._write_ai_result('skipped', 'เรียก AI ไม่สำเร็จ จึงข้ามการตรวจรอบนี้')
                continue

            reason = (result.get('reason') or '').strip()
            if result.get('match') and result.get('clear', True):
                order._write_ai_result('ok', reason or 'หมายเหตุสอดคล้องกับประเภทการจัดส่งสินค้า')
                continue

            order._write_ai_result('pending', reason)
            raise ValidationError(_(
                'หมายเหตุไม่สอดคล้องกับประเภทการจัดส่งสินค้าที่เลือก\n\n'
                'ประเภทที่เลือก: %s\n'
                'หมายเหตุที่กรอก: %s\n\n'
                'AI ตรวจแล้วพบว่า: %s\n\n'
                'กรุณาแก้หมายเหตุให้ตรงกับงานที่จะทำจริง แล้วบันทึกอีกครั้ง'
            ) % (PURPOSE_LABELS.get(purpose, purpose), note,
                 reason or 'เนื้อความไม่ตรงกับประเภทที่เลือก หรืออ่านแล้วไม่ชัดเจน'))

    def _write_ai_result(self, state, feedback):
        """เขียนผลตรวจตรงลงฐาน (ไม่ผ่าน ORM write) กันวนกลับมาตรวจซ้ำ"""
        self.ensure_one()
        self.env.cr.execute(
            'UPDATE sale_order SET shipment_note_ai_state = %s, shipment_note_ai_feedback = %s WHERE id = %s',
            (state, feedback or None, self.id),
        )
        self.invalidate_cache(['shipment_note_ai_state', 'shipment_note_ai_feedback'], self.ids)

    def _build_note_ai_prompt(self, purpose, note):
        return (
            'คุณคือผู้ตรวจเอกสารงานขนส่งของบริษัทให้เช่าอุปกรณ์ก่อสร้าง\n'
            'พนักงานเลือก "ประเภทการจัดส่งสินค้า" ไว้ แล้วพิมพ์ "หมายเหตุ" อธิบายงาน\n'
            'ให้ตรวจว่าหมายเหตุอธิบายงานแบบเดียวกับประเภทที่เลือกหรือไม่ และอ่านแล้วเข้าใจหรือไม่\n\n'
            'ความหมายของแต่ละประเภท\n'
            '- จัดส่งสินค้าไปยังลูกค้า: เอาของจากสาขาไปส่งให้ลูกค้า\n'
            '- รับสินค้าจากลูกค้ามายังสาขา: ไปรับของคืนจากลูกค้ากลับเข้าสาขา\n'
            '- โยกสินค้าจากสาขา ไปสาขา: ย้ายของระหว่างสาขาของบริษัทเอง ไม่เกี่ยวกับลูกค้า\n'
            '- ส่งรถไปช่วยขนส่งอีกสาขา: ให้ยืมรถ/คนขับไปช่วยงานของสาขาอื่น\n\n'
            'ประเภทที่เลือก: %s\n'
            'หมายเหตุของพนักงาน: %s\n\n'
            'ตอบกลับเป็น JSON เท่านั้น รูปแบบ\n'
            '{"match": true, "clear": true, "reason": "เหตุผลสั้น ๆ ภาษาไทย ไม่เกิน 2 บรรทัด"}\n'
            'match = หมายเหตุไปทางเดียวกับประเภทที่เลือก\n'
            'clear = อ่านแล้วเข้าใจว่าจะไปทำอะไร ที่ไหน (ไม่ใช่ข้อความมั่ว เช่น "-", "ทดสอบ", "asdf")\n'
            'ถ้า match เป็น false ให้บอกในเหตุผลว่าหมายเหตุดูเหมือนงานประเภทใดมากกว่า'
        ) % (PURPOSE_LABELS.get(purpose, purpose), note)
