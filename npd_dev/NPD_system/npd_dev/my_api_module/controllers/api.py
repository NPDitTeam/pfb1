from odoo import http
from odoo.http import request
import json

class SaleOrderAPI(http.Controller):

    @http.route('/api/get_sale_order', type="json", methods=['POST'], auth="user", csrf=False)
    def get_sale_order(self, **rec):
        """ API ดึงข้อมูล Sale Order ใช้ JSON และตรวจสอบฐานข้อมูลของผู้ใช้ """

        # ✅ Debug - ตรวจสอบค่าที่ได้รับจาก JSON
        # print("🔍 Raw Data:", rec)

        # ✅ ตรวจสอบว่ามีค่าหรือไม่
        so_number = rec.get('so_number', '').strip()
        database_selection = rec.get('database_selection', '').strip()

        # ✅ Debug - ตรวจสอบค่าหลังจาก clean ข้อมูล
        # print("✅ so_number:", so_number)
        # print("✅ database_selection:", database_selection)

        if not so_number or not database_selection:
            # print("❌ ข้อมูลไม่ครบถ้วน")
            return {
                "status": 400,
                "error": "กรุณาระบุ so_number และ database_selection"
            }

        # ✅ ตรวจสอบฐานข้อมูลที่ผู้ใช้ล็อกอิน
        current_db = request.env.cr.dbname  # ฐานข้อมูลที่กำลังใช้งาน
        # print("🔍 Current DB:", current_db)

        if current_db != database_selection:
            # print("❌ Database ไม่ตรงกัน")
            return {
                "status": 403,
                "error": "คุณไม่มีสิทธิ์เข้าถึงฐานข้อมูลนี้"
            }

        # ✅ ค้นหา Sale Order และตรวจสอบว่าเป็นของผู้ใช้ที่ล็อกอินหรือไม่
        user = request.env.user
        # print("🔍 Current User:", user.name)

        sale_order = request.env['sale.order'].search([('name', '=', so_number)], limit=1)

        # ✅ Debug - ตรวจสอบผลลัพธ์การค้นหา
        # print("🔍 ค้นหา SO:", sale_order)

        if not sale_order:
            # print(f"❌ ไม่พบ SO: {so_number} หรือคุณไม่มีสิทธิ์เข้าถึง")
            return {
                "status": 404,
                "error": f"ไม่พบ SO {so_number} หรือคุณไม่มีสิทธิ์เข้าถึง"
            }

        # ✅ จัดรูปแบบข้อมูลที่จะส่งกลับ
        sale_order_data = {
            "so_id": sale_order.id,
            "so_number": sale_order.name,
            "pickup_location": sale_order.pickup_location if hasattr(sale_order, 'pickup_location') else None,
            "destination": sale_order.destination if hasattr(sale_order, 'destination') else None,
            "vehicle_type_name": sale_order.vehicle_type_id.name if hasattr(sale_order, 'name') else None,
            "shipping_cost": sale_order.shipping_cost if hasattr(sale_order, 'shipping_cost') else None,
            "distance_km": sale_order.distance_km if hasattr(sale_order, 'distance_km') else None,
            "delivery_employee": sale_order.delivery_employee_id.name if sale_order.delivery_employee_id else None,
            "license_plate": sale_order.license_plate_id.name if sale_order.license_plate_id else None,
            "profit_per_trip_p": sale_order.profit_per_trip_p if hasattr(sale_order, 'profit_per_trip_p') else None,
            "profit_per_trip": sale_order.profit_per_trip if hasattr(sale_order, 'profit_per_trip') else None,
            "shipping_cost_m": sale_order.shipping_cost_m if hasattr(sale_order, 'shipping_cost_m') else None,
            "delivery_type": sale_order.delivery_type if hasattr(sale_order, 'delivery_type') else None,
            "trip_allowance": sale_order.trip_allowance if hasattr(sale_order, 'trip_allowance') else None,
            "daily_allowance": sale_order.daily_allowance if hasattr(sale_order, 'daily_allowance') else None,
            "use_special_delivery_zero": sale_order.use_special_delivery_zero if hasattr(sale_order, 'use_special_delivery_zero') else None,
            "sale_order_lines": [
                {
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.name,
                    "default_code": line.product_id.default_code,
                    'pfb_quantity': line.pfb_quantity,  # ✅ ใช้ `line.pfb_quantity` ไม่ใช่ `line.product_id.pfb_quantity`
                    'total_weight': line.pfb_quantity * line.second_uom_qty,  # ✅ คำนวณจาก `line`
                    'second_uom_qty': line.second_uom_qty,  # ✅ ใช้จาก `line`
                }
                for line in sale_order.order_line
            ]
        }

        # print("✅ ค้นหา SO สำเร็จ, ส่งข้อมูลกลับ:", sale_order_data)

        return {
            "status": 200,
            "result": sale_order_data,
            "message": "Success"
        }
