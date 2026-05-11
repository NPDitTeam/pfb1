from odoo import http
from odoo.http import request
import logging
from collections import defaultdict
import time
import uuid

_logger = logging.getLogger(__name__)

class StockAPIController(http.Controller):

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
                    _logger.warning("⚠️ ข้อมูลไม่ครบ default_code=%s, source_location_id=%s, qty=%s",
                                    default_code, source_location_id, qty)
                    continue

                # ค้นหา product
                product_template = request.env['product.template'].sudo().search([
                    ('default_code', 'ilike', default_code)
                ], limit=1)

                if not product_template or not product_template.product_variant_id:
                    _logger.warning("❌ ไม่พบสินค้าใน product.template ที่ default_code ilike '%s'", default_code)
                    continue

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
                        _logger.info("✅ Picking validated: %s", picking.name)
                        created_docs.append(picking.name)
                    except Exception as e:
                        _logger.error("❌ Error during validate picking_id %s: %s", picking.id, str(e))
                        return {'status': 500, 'error': f'Validation Error: {str(e)}'}

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
                    _logger.info("🗑️ Scrap created and validated for %s", product.display_name)
                    created_docs.append(scrap.name or f"Scrap-{product.default_code}")

            return {
                'status': 200,
                'message': 'Transfer/Scrap completed',
                'documents': created_docs
            }

        except Exception as e:
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
                    _logger.warning("⚠️ ข้อมูลไม่ครบ: default_code=%s, source=%s, qty=%s",
                                    default_code, source_location_id, qty)
                    continue

                # ✅ หา product จาก default_code
                product_template = request.env['product.template'].sudo().search([
                    ('default_code', 'ilike', default_code)
                ], limit=1)
                if not product_template or not product_template.product_variant_id:
                    _logger.warning("❌ ไม่พบสินค้า: %s", default_code)
                    continue

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
                        _logger.info("✅ Picking Validated: %s", picking.name)
                        rolled_back.append(picking.name)
                    except Exception as e:
                        _logger.error("❌ Validate Error for picking_id %s: %s", picking.id, str(e))
                        return {'status': 500, 'error': f'Rollback Validation Error: {str(e)}'}

                else:
                    # ❌ ไม่มีปลายทาง → เติม stock กลับต้นทางด้วย stock.quant
                    quant = request.env['stock.quant'].sudo().search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', source_location_id)
                    ], limit=1)

                    if quant:
                        quant.quantity += qty
                        _logger.info("🟢 เพิ่ม stock.quant: %s @ %s +%.2f", product.display_name,
                                     quant.location_id.display_name, qty)
                    else:
                        request.env['stock.quant'].sudo().create({
                            'product_id': product.id,
                            'location_id': source_location_id,
                            'quantity': qty
                        })
                        _logger.info("🟢 สร้าง stock.quant ใหม่: %s @ %s +%.2f", product.display_name,
                                     source_location_id, qty)

                    rolled_back.append(f"quant-{product.default_code or product.id}")

            return {
                'status': 200,
                'message': 'Rollback completed',
                'pickings': rolled_back
            }

        except Exception as e:
            _logger.exception("❌ ROLLBACK ERROR")
            return {'status': 500, 'error': str(e)}

