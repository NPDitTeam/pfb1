from odoo import http
from odoo.http import request
import logging
from collections import defaultdict
import time
import uuid

_logger = logging.getLogger(__name__)

class StockAPIController(http.Controller):

    def _fail(self, message):
        """ยกเลิกทุกอย่างที่ทำไปแล้วใน request นี้ แล้วคืน error

        เดิมโค้ดใช้ `continue` ข้ามรายการที่มีปัญหาแล้วยังตอบ 200 ทำให้ฝั่งที่เรียก
        เติมสต๊อกปลายทางครบทุกบรรทัดทั้งที่ต้นทางตัดไม่ครบ = ของงอก
        """
        request.env.cr.rollback()
        _logger.error("❌ %s", message)
        return {'status': 500, 'error': message}

    def _onhand_qty(self, product, location_id):
        quants = request.env['stock.quant'].sudo().search([
            ('product_id', '=', product.id),
            ('location_id', '=', location_id),
        ])
        return sum(quants.mapped('quantity'))

    @http.route('/api/get_stock', type='json', auth='user', methods=['POST'], csrf=False)
    def get_stock_info(self):
        try:
            quants = request.env['stock.quant'].sudo().search([
                ('product_id.product_tmpl_id.route_ids.name', '=', 'ขอเบิก')
            ])
            total_quantities = defaultdict(float)

            for q in quants:
                total_quantities[q.product_id.id] += q.quantity

            result = []
            for q in quants:
                result.append({
                    'product_id': q.product_id.id,
                    'product_name': q.product_id.name,
                    'location_id': q.location_id.id,
                    'location': q.location_id.complete_name,
                    'quantity': q.quantity,
                    'default_code' : q.product_id.default_code,
                    'total_qty_all_locations': total_quantities[q.product_id.id]
                })

            return {
                'status': 200,
                'result': result
            }

        except Exception as e:
            _logger.exception("❌ ERROR get_stock_info")
            return {'status': 500, 'error': str(e)}

    @http.route('/api/transfer_stock', type='json', auth='user', methods=['POST'], csrf=False)
    def transfer_stock(self):
        try:
            post = request.jsonrequest
            transfers = post.get('transfers', [])
            if not transfers:
                return {'status': 400, 'error': 'Missing transfer data'}

            picking_type = request.env['stock.picking.type'].sudo().search([('code', '=', 'internal')], limit=1)
            if not picking_type:
                return {'status': 404, 'error': 'ไม่พบ picking type แบบ internal'}

            created_docs = []

            for transfer in transfers:
                default_code = transfer.get('default_code')
                source_location_id = transfer.get('source_location_id')
                destination_location_id = transfer.get('destination_location_id')  # optional
                qty = transfer.get('qty')

                if not all([default_code, source_location_id, qty]):
                    return self._fail(
                        "ข้อมูลไม่ครบ: default_code=%s, source_location_id=%s, qty=%s"
                        % (default_code, source_location_id, qty))

                # ค้นหา product — จับตรงตัวก่อน แล้วค่อย fallback เป็น ilike
                # (ilike เป็น substring match อาจไปโดนรหัสอื่นที่มีรหัสนี้เป็นส่วนหนึ่ง)
                ProductTemplate = request.env['product.template'].sudo()
                product_template = ProductTemplate.search([('default_code', '=', default_code)], limit=1)
                if not product_template:
                    product_template = ProductTemplate.search([('default_code', 'ilike', default_code)], limit=1)

                if not product_template or not product_template.product_variant_id:
                    return self._fail("ไม่พบสินค้ารหัส '%s' ในฐานข้อมูลต้นทาง" % default_code)

                product = product_template.product_variant_id

                # ✅ กรณีมี destination_location_id → ใช้ Picking
                if destination_location_id and destination_location_id != source_location_id:
                    picking_name = request.env['ir.sequence'].next_by_code('W1/INT') or f"API-PICK-{uuid.uuid4().hex[:8].upper()}"
                    while request.env['stock.picking'].sudo().search([('name', '=', picking_name)], limit=1):
                        picking_name = f"API-PICK-{uuid.uuid4().hex[:8].upper()}"

                    picking = request.env['stock.picking'].sudo().create({
                        'name': picking_name,
                        'picking_type_id': picking_type.id,
                        'location_id': source_location_id,
                        'location_dest_id': destination_location_id,
                        'origin': f"API-{product.default_code}",
                        'move_lines': [(0, 0, {
                            'name': product.display_name or 'API Transfer',
                            'product_id': product.id,
                            'product_uom_qty': qty,
                            'product_uom': product.uom_id.id,
                            'location_id': source_location_id,
                            'location_dest_id': destination_location_id,
                            'picking_type_id': picking_type.id,
                            'company_id': request.env.company.id
                        })]
                    })

                    _logger.info("✅ Created Picking: %s", picking.name)

                    try:
                        picking.action_confirm()
                        picking.action_assign()
                        for move in picking.move_lines:
                            move.quantity_done = qty
                        picking.button_validate()
                    except Exception as e:
                        _logger.error("❌ Error during validate picking_id %s: %s", picking.id, str(e))
                        return self._fail('Validation Error: %s' % str(e))

                    # button_validate อาจคืน wizard (immediate/backorder) แทนที่จะย้ายของจริง
                    # ต้องเช็ค state เสมอ ห้ามถือว่าเรียกแล้วสำเร็จ
                    if picking.state != 'done':
                        return self._fail(
                            "ใบโอน %s ไม่สำเร็จ (state=%s) — สต๊อก %s ที่คลัง id=%s มี %.2f แต่ขอ %.2f"
                            % (picking.name, picking.state, product.default_code,
                               source_location_id, self._onhand_qty(product, source_location_id), qty))

                    _logger.info("✅ Picking validated: %s", picking.name)
                    created_docs.append(picking.name)

                # ❌ ไม่มี destination → ตัดสต๊อกด้วย scrap
                else:
                    scrap = request.env['stock.scrap'].sudo().create({
                        'product_id': product.id,
                        'product_uom_id': product.uom_id.id,
                        'scrap_qty': qty,
                        'location_id': source_location_id,
                        'origin': f"API-SCRAP-{product.default_code}"
                    })
                    scrap.action_validate()

                    # ⚠️ จุดที่ทำให้ของงอกมาตลอด: ถ้าของไม่พอ action_validate() จะคืน dict ของ
                    # wizard "Insufficient Quantity To Scrap" โดยไม่ตัดของ แล้ว scrap ค้าง draft
                    # ของเดิมไม่ได้เช็คค่านี้เลย เลยตอบ 200 ทั้งที่ต้นทางไม่ถูกตัด
                    if scrap.state != 'done':
                        return self._fail(
                            "ตัดสต๊อก %s ไม่สำเร็จ (scrap state=%s) — คลัง id=%s มี %.2f แต่ขอ %.2f"
                            % (product.default_code, scrap.state, source_location_id,
                               self._onhand_qty(product, source_location_id), qty))

                    _logger.info("🗑️ Scrap created and validated for %s", product.display_name)
                    created_docs.append(scrap.name or f"Scrap-{product.default_code}")

            if len(created_docs) != len(transfers):
                return self._fail("สร้างเอกสารได้ไม่ครบ (ขอ %d รายการ ได้ %d รายการ)"
                                  % (len(transfers), len(created_docs)))

            return {
                'status': 200,
                'message': 'Transfer/Scrap completed',
                'documents': created_docs,
                'all_done': True,
            }

        except Exception as e:
            request.env.cr.rollback()
            _logger.exception("❌ TRANSFER ERROR")
            return {'status': 500, 'error': str(e)}

    @http.route('/api/rollback_stock', type='json', auth='user', methods=['POST'], csrf=False)
    def rollback_stock(self):
        try:
            post = request.jsonrequest
            transfers = post.get('transfers', [])
            if not transfers:
                return {'status': 400, 'error': 'Missing rollback data'}

            picking_type = request.env['stock.picking.type'].sudo().search([('code', '=', 'internal')], limit=1)
            if not picking_type:
                return {'status': 404, 'error': 'ไม่พบ picking type แบบ internal'}

            rolled_back = []

            for transfer in transfers:
                default_code = transfer.get('default_code')
                original_source = transfer.get('source_location_id')  # ฝั่งที่ส่งมาคือ source เดิม
                original_dest = transfer.get('destination_location_id')  # อาจไม่มี
                qty = transfer.get('qty')

                # 🔁 กลับทิศการคืนของ
                source_location_id = original_dest if original_dest else original_source
                destination_location_id = original_source if original_dest else None

                if not all([default_code, source_location_id, qty]):
                    return self._fail("ข้อมูลไม่ครบ: default_code=%s, source=%s, qty=%s"
                                      % (default_code, source_location_id, qty))

                # ✅ หา product จาก default_code — จับตรงตัวก่อน แล้วค่อย fallback เป็น ilike
                ProductTemplate = request.env['product.template'].sudo()
                product_template = ProductTemplate.search([('default_code', '=', default_code)], limit=1)
                if not product_template:
                    product_template = ProductTemplate.search([('default_code', 'ilike', default_code)], limit=1)
                if not product_template or not product_template.product_variant_id:
                    return self._fail("ไม่พบสินค้ารหัส '%s' ในฐานข้อมูลต้นทาง" % default_code)

                product = product_template.product_variant_id

                # ✅ ถ้ามี destination จริง และต่างจากต้นทาง → ใช้ stock.picking
                if destination_location_id and source_location_id != destination_location_id:
                    picking_name = f"ROLLBACK-API-{product.default_code or 'N/A'}-{uuid.uuid4().hex[:8].upper()}"
                    while request.env['stock.picking'].sudo().search([('name', '=', picking_name)], limit=1):
                        picking_name = f"ROLLBACK-API-{product.default_code or 'N/A'}-{uuid.uuid4().hex[:8].upper()}"

                    picking = request.env['stock.picking'].sudo().create({
                        'name': picking_name,
                        'picking_type_id': picking_type.id,
                        'location_id': source_location_id,
                        'location_dest_id': destination_location_id,
                        'origin': f"ROLLBACK-API-{product.default_code or 'N/A'}",
                        'move_lines': [(0, 0, {
                            'name': product.display_name or 'Rollback Transfer',
                            'product_id': product.id,
                            'product_uom_qty': qty,
                            'product_uom': product.uom_id.id,
                            'location_id': source_location_id,
                            'location_dest_id': destination_location_id,
                            'picking_type_id': picking_type.id,
                            'company_id': request.env.company.id
                        })]
                    })

                    _logger.info("🔄 Created Rollback Picking: %s", picking.name)

                    try:
                        picking.action_confirm()
                        picking.action_assign()
                        for move in picking.move_lines:
                            move.quantity_done = qty
                        picking.button_validate()
                    except Exception as e:
                        _logger.error("❌ Validate Error for picking_id %s: %s", picking.id, str(e))
                        return self._fail('Rollback Validation Error: %s' % str(e))

                    if picking.state != 'done':
                        return self._fail("ใบคืนของ %s ไม่สำเร็จ (state=%s)" % (picking.name, picking.state))

                    _logger.info("✅ Picking Validated: %s", picking.name)
                    rolled_back.append(picking.name)

                else:
                    # ❌ ไม่มีปลายทาง = ตอนโอนออกใช้ scrap → คืนของต้องดึงกลับจากคลัง Scrap
                    # เดิมเขียน quant.quantity += qty ตรงๆ ทำให้ใบ scrap ยังค้างเป็นของเสีย
                    # แต่ของกลับมาเต็มจำนวน = เสกของขึ้นมาใหม่ทุกครั้งที่กดยกเลิก
                    scrap_location = request.env['stock.location'].sudo().search([
                        ('scrap_location', '=', True),
                        '|', ('company_id', '=', request.env.company.id), ('company_id', '=', False),
                    ], limit=1)
                    if not scrap_location:
                        return self._fail("ไม่พบคลัง Scrap สำหรับคืนของ")

                    picking_name = f"ROLLBACK-SCRAP-{product.default_code or 'N/A'}-{uuid.uuid4().hex[:8].upper()}"
                    picking = request.env['stock.picking'].sudo().create({
                        'name': picking_name,
                        'picking_type_id': picking_type.id,
                        'location_id': scrap_location.id,
                        'location_dest_id': source_location_id,
                        'origin': f"ROLLBACK-SCRAP-{product.default_code or 'N/A'}",
                        'move_lines': [(0, 0, {
                            'name': product.display_name or 'Rollback Scrap',
                            'product_id': product.id,
                            'product_uom_qty': qty,
                            'product_uom': product.uom_id.id,
                            'location_id': scrap_location.id,
                            'location_dest_id': source_location_id,
                            'picking_type_id': picking_type.id,
                            'company_id': request.env.company.id
                        })]
                    })

                    try:
                        picking.action_confirm()
                        picking.action_assign()
                        for move in picking.move_lines:
                            move.quantity_done = qty
                        picking.button_validate()
                    except Exception as e:
                        _logger.error("❌ Validate Error for rollback-scrap picking %s: %s", picking.id, str(e))
                        return self._fail('Rollback Validation Error: %s' % str(e))

                    if picking.state != 'done':
                        return self._fail("ใบคืนของจาก Scrap %s ไม่สำเร็จ (state=%s)"
                                          % (picking.name, picking.state))

                    _logger.info("🟢 คืนของจาก Scrap: %s +%.2f (%s)", product.display_name, qty, picking.name)
                    rolled_back.append(picking.name)

            if len(rolled_back) != len(transfers):
                return self._fail("คืนของได้ไม่ครบ (ขอ %d รายการ ได้ %d รายการ)"
                                  % (len(transfers), len(rolled_back)))

            return {
                'status': 200,
                'message': 'Rollback completed',
                'pickings': rolled_back,
                'documents': rolled_back,
                'all_done': True,
            }

        except Exception as e:
            request.env.cr.rollback()
            _logger.exception("❌ ROLLBACK ERROR")
            return {'status': 500, 'error': str(e)}

