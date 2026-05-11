# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class SaleOrderAPIController(http.Controller):

    def _get_shipment_info(self, order):
        """
        ฟังก์ชันสำหรับดึงข้อมูล ShipmentInformation แบบครบถ้วน
        """
        shipment_info = {
            # 🚚 ข้อมูลการขนส่งพื้นฐาน
            'basic': {
                'pickup_location': order.pickup_location if hasattr(order, 'pickup_location') else None,
                'destination': order.destination if hasattr(order, 'destination') else None,
                'vehicle_type_id': order.vehicle_type_id.id if hasattr(order, 'vehicle_type_id') and order.vehicle_type_id else None,
                'vehicle_type_name': order.vehicle_type_id.name if hasattr(order, 'vehicle_type_id') and order.vehicle_type_id else None,
                'distance_km': order.distance_km if hasattr(order, 'distance_km') else None,
                'shipping_cost_raw': order.shipping_cost_raw if hasattr(order, 'shipping_cost_raw') else None,
                'shipping_cost': order.shipping_cost if hasattr(order, 'shipping_cost') else None,
                'shipping_cost_m': order.shipping_cost_m if hasattr(order, 'shipping_cost_m') else None,
                'delivery_type': order.delivery_type if hasattr(order, 'delivery_type') else None,
                'trip_allowance': order.trip_allowance if hasattr(order, 'trip_allowance') else None,
                'daily_allowance': order.daily_allowance if hasattr(order, 'daily_allowance') else None,
                'use_special_delivery_zero': order.use_special_delivery_zero if hasattr(order, 'use_special_delivery_zero') else None,
            },

            # 👤 ข้อมูลพนักงานและรถ
            'vehicle_assignment': {
                'delivery_employee_id': order.delivery_employee_id.id if hasattr(order, 'delivery_employee_id') and order.delivery_employee_id else None,
                'delivery_employee_name': order.delivery_employee_id.name if hasattr(order, 'delivery_employee_id') and order.delivery_employee_id else None,
                'license_plate_id': order.license_plate_id.id if hasattr(order, 'license_plate_id') and order.license_plate_id else None,
                'license_plate_name': order.license_plate_id.name if hasattr(order, 'license_plate_id') and order.license_plate_id else None,
            },

            # ⛽ ข้อมูลค่าน้ำมัน
            'fuel': {
                'fuel_price_per_liter': order.fuel_price_per_liter if hasattr(order, 'fuel_price_per_liter') else None,
                'fuel_consumption_rate': order.fuel_consumption_rate if hasattr(order, 'fuel_consumption_rate') else None,
                'fuel_used_per_trip': order.fuel_used_per_trip if hasattr(order, 'fuel_used_per_trip') else None,
                'fuel_cost_per_trip': order.fuel_cost_per_trip if hasattr(order, 'fuel_cost_per_trip') else None,
            },

            # 📉 ข้อมูลค่าเสื่อมราคา
            'depreciation': {
                'vehicle': order.vehicle if hasattr(order, 'vehicle') else None,
                'vehicle_cost': order.vehicle_cost if hasattr(order, 'vehicle_cost') else None,
                'salvage_value': order.salvage_value if hasattr(order, 'salvage_value') else None,
                'depreciation_period': order.depreciation_period if hasattr(order, 'depreciation_period') else None,
                'depreciation_per_trip': order.depreciation_per_trip if hasattr(order, 'depreciation_per_trip') else None,
            },

            # 💰 ค่าใช้จ่ายประจำปี
            'annual_expenses': {
                'annual_vehicle_tax_y': order.annual_vehicle_tax_y if hasattr(order, 'annual_vehicle_tax_y') else None,
                'annual_vehicle_tax': order.annual_vehicle_tax if hasattr(order, 'annual_vehicle_tax') else None,
                'annual_insurance_class2': order.annual_insurance_class2 if hasattr(order, 'annual_insurance_class2') else None,
                'annual_insurance_class1': order.annual_insurance_class1 if hasattr(order, 'annual_insurance_class1') else None,
                'annual_compulsory_insurance1': order.annual_compulsory_insurance1 if hasattr(order, 'annual_compulsory_insurance1') else None,
                'annual_compulsory_insurance': order.annual_compulsory_insurance if hasattr(order, 'annual_compulsory_insurance') else None,
                'total_depreciation_per_trip': order.total_depreciation_per_trip if hasattr(order, 'total_depreciation_per_trip') else None,
            },

            # 👷 ข้อมูลค่าแรงงาน
            'labor': {
                'labor_costs': order.labor_costs if hasattr(order, 'labor_costs') else None,
                'working_days_per_month': order.working_days_per_month if hasattr(order, 'working_days_per_month') else None,
                'driver_salary': order.driver_salary if hasattr(order, 'driver_salary') else None,
                'maintenance_cost': order.maintenance_cost if hasattr(order, 'maintenance_cost') else None,
                'trips_per_day': order.trips_per_day if hasattr(order, 'trips_per_day') else None,
                'labor_cost_per_trip': order.labor_cost_per_trip if hasattr(order, 'labor_cost_per_trip') else None,
                'total_labor_per_trip': order.total_labor_per_trip if hasattr(order, 'total_labor_per_trip') else None,
            },

            # 📋 ค่าใช้จ่ายอื่นๆ
            'other_expenses': {
                'other_expenses': order.other_expenses if hasattr(order, 'other_expenses') else None,
            },

            # 📊 สรุปต้นทุนและกำไร
            'cost_summary': {
                'total_cost_per_trip': order.total_cost_per_trip if hasattr(order, 'total_cost_per_trip') else None,
                'profit_per_trip': order.profit_per_trip if hasattr(order, 'profit_per_trip') else None,
                'profit_per_trip_p': order.profit_per_trip_p if hasattr(order, 'profit_per_trip_p') else None,
            },
        }

        return shipment_info

    @http.route('/api/sale_orders', type='json', auth='user', methods=['POST'], csrf=False)
    def get_sale_orders(self, **kwargs):
        """
        🚚 API สำหรับดึงข้อมูล Sale Order พร้อมข้อมูลการจัดส่งและสินค้า

        📋 Parameters (optional):
        - order_ids: [1,2,3] - รายการ ID ของ Sale Order
        - state: 'draft', 'sent', 'sale', 'done', 'cancel'
        - date_from: '2025-01-01' - วันที่เริ่มต้น (YYYY-MM-DD)
        - date_to: '2025-12-31' - วันที่สิ้นสุด (YYYY-MM-DD)
        - partner_id: 123 - ID ของลูกค้า
        - limit: 100 - จำนวนรายการสูงสุด (default: 100)
        - offset: 0 - เริ่มต้นจากรายการที่ (default: 0)

        ✅ Returns:
        {
            "success": true,
            "data": [...],
            "count": 10,
            "total": 150,
            "message": "ดึงข้อมูลสำเร็จ"
        }
        """
        try:
            # รับ parameters
            order_ids = kwargs.get('order_ids', [])
            state = kwargs.get('state')
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            partner_id = kwargs.get('partner_id')
            limit = kwargs.get('limit', 100)
            offset = kwargs.get('offset', 0)

            # สร้าง domain สำหรับค้นหา
            domain = []

            if order_ids:
                domain.append(('id', 'in', order_ids))

            if state:
                domain.append(('state', '=', state))

            if date_from:
                domain.append(('date_order', '>=', date_from))

            if date_to:
                domain.append(('date_order', '<=', date_to))

            if partner_id:
                domain.append(('partner_id', '=', partner_id))

            # ค้นหา Sale Orders
            SaleOrder = request.env['sale.order'].sudo()
            orders = SaleOrder.search(domain, limit=limit, offset=offset, order='date_order desc')
            total_count = SaleOrder.search_count(domain)

            # เตรียมข้อมูล
            result = []
            for order in orders:

                # ข้อมูลสินค้า
                order_lines = []
                for line in order.order_line:
                    order_lines.append({
                        'id': line.id,
                        'product_id': line.product_id.id if line.product_id else None,
                        'product_name': line.product_id.name if line.product_id else None,
                        'product_code': line.product_id.default_code if line.product_id else None,
                        'description': line.name or '',
                        'quantity': line.product_uom_qty,
                        'uom': line.product_uom.name if line.product_uom else None,
                        'price_unit': line.price_unit,
                        'discount': line.discount,
                        'price_subtotal': line.price_subtotal,
                        'price_tax': line.price_tax,
                        'price_total': line.price_total,
                        'total_weight': line.total_weight,
                    })

                # ข้อมูล Sale Order
                order_data = {
                    # ข้อมูลพื้นฐาน
                    'id': order.id,
                    'name': order.name,
                    'branch_id': order.branch_id.name,
                    'state': order.state,
                    'state_text': dict(order._fields['state'].selection).get(order.state),
                    'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,
                    'validity_date': order.validity_date.strftime('%Y-%m-%d') if order.validity_date else None,

                    # ข้อมูลลูกค้า
                    'partner_id': order.partner_id.id if order.partner_id else None,
                    'partner_name': order.partner_id.name if order.partner_id else None,
                    'partner_phone': order.partner_id.phone if order.partner_id else None,
                    'partner_email': order.partner_id.email if order.partner_id else None,

                    # 🚚 ข้อมูลการขนส่งแบบครบถ้วน
                    'shipment_information': self._get_shipment_info(order),

                    # ข้อมูลการเงิน
                    'amount_untaxed': order.amount_untaxed,
                    'amount_tax': order.amount_tax,
                    'amount_total': order.amount_total,
                    'currency': order.currency_id.name if order.currency_id else 'THB',

                    # ข้อมูลเพิ่มเติม
                    'user_id': order.user_id.id if order.user_id else None,
                    'salesperson_name': order.user_id.name if order.user_id else None,
                    'company_id': order.company_id.id if order.company_id else None,
                    'company_name': order.company_id.name if order.company_id else None,
                    'note': order.note or '',
                    'is_renew_green_house': order.is_renew_green_house if hasattr(order, 'is_renew_green_house') else False,

                    # รายการสินค้า
                    'order_lines': order_lines,
                    'order_lines_count': len(order_lines),
                }

                result.append(order_data)

            return {
                'success': True,
                'data': result,
                'count': len(result),
                'total': total_count,
                'message': f'ดึงข้อมูลสำเร็จ {len(result)} รายการจากทั้งหมด {total_count} รายการ'
            }

        except Exception as e:
            _logger.error(f'❌ Error in get_sale_orders: {str(e)}', exc_info=True)
            return {
                'success': False,
                'data': [],
                'count': 0,
                'total': 0,
                'message': f'เกิดข้อผิดพลาด: {str(e)}'
            }

    @http.route('/api/sale_order/<int:order_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_sale_order_detail(self, order_id, **kwargs):
        """
        📄 API สำหรับดึงข้อมูล Sale Order รายการเดียว

        Parameters:
        - order_id: ID ของ Sale Order

        Returns: รายละเอียดของ Sale Order
        """
        try:
            order = request.env['sale.order'].sudo().browse(order_id)

            if not order.exists():
                return {
                    'success': False,
                    'data': None,
                    'message': f'ไม่พบ Sale Order ID: {order_id}'
                }

            # ข้อมูลสินค้า
            order_lines = []
            for line in order.order_line:
                order_lines.append({
                    'id': line.id,
                    'product_id': line.product_id.id if line.product_id else None,
                    'product_name': line.product_id.name if line.product_id else None,
                    'product_code': line.product_id.default_code if line.product_id else None,
                    'description': line.name or '',
                    'quantity': line.product_uom_qty,
                    'uom': line.product_uom.name if line.product_uom else None,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'price_subtotal': line.price_subtotal,
                    'price_tax': line.price_tax,
                    'price_total': line.price_total,
                    'total_weight': line.total_weight,
                })

            order_data = {
                # ข้อมูลพื้นฐาน
                'id': order.id,
                'name': order.name,
                'branch_id': order.branch_id.name,
                'state': order.state,
                'state_text': dict(order._fields['state'].selection).get(order.state),
                'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,

                # ข้อมูลลูกค้า
                'partner_id': order.partner_id.id if order.partner_id else None,
                'partner_name': order.partner_id.name if order.partner_id else None,
                'partner_phone': order.partner_id.phone if order.partner_id else None,
                'partner_email': order.partner_id.email if order.partner_id else None,

                # 🚚 ข้อมูลการขนส่งแบบครบถ้วน
                'shipment_information': self._get_shipment_info(order),

                # ข้อมูลการเงิน
                'amount_untaxed': order.amount_untaxed,
                'amount_tax': order.amount_tax,
                'amount_total': order.amount_total,
                'currency': order.currency_id.name if order.currency_id else 'THB',

                # ข้อมูลเพิ่มเติม
                'user_id': order.user_id.id if order.user_id else None,
                'salesperson_name': order.user_id.name if order.user_id else None,
                'note': order.note or '',
                'is_renew_green_house': order.is_renew_green_house if hasattr(order, 'is_renew_green_house') else False,

                # รายการสินค้า
                'order_lines': order_lines,
                'order_lines_count': len(order_lines),
            }

            return {
                'success': True,
                'data': order_data,
                'message': 'ดึงข้อมูลสำเร็จ'
            }

        except Exception as e:
            _logger.error(f'❌ Error in get_sale_order_detail: {str(e)}', exc_info=True)
            return {
                'success': False,
                'data': None,
                'message': f'เกิดข้อผิดพลาด: {str(e)}'
            }