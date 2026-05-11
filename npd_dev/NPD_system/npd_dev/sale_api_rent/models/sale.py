import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # database_selection = fields.Selection([
    #     ('test_2025_import004', 'test_2025_import004'),
    #     ('test_2025_import003', 'test_2025_import003')
    # ], string="ดึงข้อมูลการเช่าจาก บ.อื่น")
    def _get_database_options(self):
        data_list = [
            ('NPD_S_Group_New_V2', 'NPD_S_Group_New_V2'),
            ('NPD_Intertrading_New', 'NPD_Intertrading_New'),
            ('NPD_Intertrading_New_NonVat', 'NPD_Intertrading_New_NonVat'),
            ('NPD_Bangkok_New', 'NPD_Bangkok_New'),
            ('test', 'test'),
            # ('TEST_New', 'TEST_New'),
        ]
        return data_list

    database_selection = fields.Selection(
        selection=_get_database_options,
        string="ดึงข้อมูลการเช่าจาก บ.อื่น"
    )

    # database_selection = fields.Selection([
    #     ('NPD_S_Group_New', 'NPD_S_Group_New'),
    #     ('NPD_Bangkok_New', 'NPD_Bangkok_New'),
    #     ('TEST_New', 'TEST_New')
    # ], string="ดึงข้อมูลการเช่าจาก บ.อื่น")

    so_number = fields.Char(string="เลขเอกสาร SO")
    is_renew_green_house = fields.Boolean(string="บิลต่ออายุจากบ้านเขียว", default=False)

    def action_fetch_rental_data(self):
        """ ดึงข้อมูลคำสั่งขายจาก API `get_sale_order` """
        if not self.database_selection or not self.so_number:
            raise UserError(_("กรุณาเลือก Database และกรอกเลข SO ก่อนดำเนินการ!"))

        # base_url = "http://127.0.0.1:8069"
        base_url = "https://npderp.com"
        api_url = f"{base_url}/api/get_sale_order"

        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})

        login_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.database_selection,
                "login": "Npd_admin",
                "password": "1234"
            }
        }
        login_response = session.post(f"{base_url}/web/session/authenticate", json=login_payload, timeout=5)
        login_response.raise_for_status()

        session_id = session.cookies.get("session_id")
        if not session_id:
            raise UserError(_("❌ ไม่พบ session_id, Login อาจล้มเหลว!"))

        session.headers.update({"Cookie": f"session_id={session_id}"})

        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "so_number": self.so_number,
                "database_selection": self.database_selection
            }
        }
        _logger.info(f"📤 ส่งข้อมูลไป API: {payload}")

        response = session.post(api_url, json=payload, timeout=10)

        _logger.info(f"📡 API Response: {response.text}")

        if response.status_code != 200:
            raise UserError(_("เกิดข้อผิดพลาดจาก API: %s") % response.text)

        try:
            data = response.json()
        except Exception as e:
            raise UserError(_("เกิดข้อผิดพลาดในการแปลง JSON: %s") % str(e))

        _logger.info(f"🔍 Raw API Response: {data}")

        if "error" in data:
            raise UserError(_("\n❌ API Error: %s") % data["error"])

        # ✅ ดึงข้อมูล Sale Order อย่างถูกต้อง
        so_data = data.get("result", {}).get("result", {})  # 🔥 แก้โครงสร้าง JSON
        sol_data = so_data.get("sale_order_lines", [])

        _logger.info(f"🔍 Debug so_data: {so_data}")
        _logger.info(f"🔍 Debug sale_order_lines: {sol_data}")

        if not sol_data:
            raise UserError(_("\n❌ ไม่พบข้อมูลสินค้าใน SO"))

        employee_name = so_data.get('delivery_employee')  # ✅ ใช้ .get() แทน []
        license_plate_name = so_data.get('license_plate')
        vehicle_type_name = so_data.get('vehicle_type_name')

        shipping_cost = self.env['shipping.cost'].search([('name', '=', vehicle_type_name)], limit=1)
        if not shipping_cost:
            raise UserError(_("\n❌ ไม่พบประเภทรถ: %s") % vehicle_type_name)

        employee = self.env['hr.employee'].search([('name', '=', employee_name)], limit=1)
        if not employee:
            raise UserError(_("\n❌ ไม่พบพนักงาน: %s") % employee_name)

        license_plate = self.env['fleet.license_plate'].search([('name', '=', license_plate_name)], limit=1)
        if not license_plate:
            raise UserError(_("\n❌ ไม่พบป้ายทะเบียน: %s") % license_plate_name)

        self.write({
            'delivery_employee_id':employee.id,
            'license_plate_id': license_plate.id,
            'pickup_location': so_data.get('pickup_location', ''),
            'destination': so_data.get('destination', ''),
            'vehicle_type_id': shipping_cost.id,
            'shipping_cost': so_data.get('shipping_cost', 0.0),
            'distance_km': so_data.get('distance_km', 0.0),
            'profit_per_trip_p': so_data.get('profit_per_trip_p', 0.0),
            'profit_per_trip': so_data.get('profit_per_trip', 0.0),
            'shipping_cost_m': so_data.get('shipping_cost_m', 0.0),
            'delivery_type': so_data.get('delivery_type'),
            'trip_allowance': so_data.get('trip_allowance'),
            'daily_allowance': so_data.get('daily_allowance'),
            'use_special_delivery_zero': so_data.get('use_special_delivery_zero', 0.0)
        })

        if self.order_line:
            _logger.info(f"🗑️ ลบรายการสินค้าเดิมใน SO: {self.name}")
            self.order_line.unlink()

        for sol in sol_data:
            product = self.env['product.product'].search([('default_code', '=', sol.get('default_code', ''))], limit=1)

            # if not product:
            #     _logger.warning(f"❌ ไม่พบสินค้าใน Odoo: {sol.get('default_code', '')}")
            #     continue
            if not product:
                raise UserError(f"❌ ไม่พบสินค้าใน Logistics_New: {sol.get('product_name', '')}")

            _logger.info(f"➕ เพิ่มสินค้า: {product.name} | จำนวน: {sol.get('quantity', 0)}")


            self.env['sale.order.line'].create({
                'order_id': self.id,
                'product_id': product.id,
                'name': product.name,
                'pfb_quantity': sol.get('pfb_quantity', 0),
                'second_uom_qty': sol.get('second_uom_qty', 1),
                'total_weight':  sol.get('total_weight', 0),
            })

        _logger.info(f"✅ บันทึกรายการสินค้าเรียบร้อย: {self.so_number}")

        return True




# # import psycopg2
# # from odoo import api, fields, models, _
# # from odoo.exceptions import UserError
# import logging
# import requests
# from odoo import api, fields, models, _
# from odoo.exceptions import UserError
#
# _logger = logging.getLogger(__name__)
#
# class SaleOrder(models.Model):
#     _inherit = "sale.order"
#
#     # # ทดสอบผ่าน localhost
#     database_selection = fields.Selection([
#         ('test_2025_import002', 'test_2025_import002'),
#         ('test_2025_import003', 'test_2025_import003')
#     ], string="ดึงข้อมูลการเช่าจาก บ.อื่น")
#
#     # database_selection = fields.Selection([
#     #     ('NPD_S_Group_New', 'NPD_S_Group_New'),
#     #     ('NPD_Bangkok_New', 'NPD_Bangkok_New'),
#     #     ('TEST_New', 'TEST_New')
#     # ], string="ดึงข้อมูลการเช่าจาก บ.อื่น")
#
#     so_number = fields.Char(string="เลขเอกสาร SO")
#
#     def action_fetch_rental_data(self):
#         """ ดึงข้อมูลคำสั่งขายจาก API """
#         if not self.database_selection or not self.so_number:
#             raise UserError(_("กรุณาเลือก Database และกรอกเลข SO ก่อนดำเนินการ!"))
#
#         url = "http://127.0.0.1:8069/api/get_sale_order"
#         params = {
#             "so_number": self.so_number,
#             "database_selection": self.database_selection
#         }
#
#         _logger.info(f"📡 Requesting API: {url} with params: {params}")
#
#         response = requests.get(url, params=params)
#
#         _logger.info(f"📝 API Response: {response.text}")
#
#         if response.status_code == 200:
#             try:
#                 data = response.json()
#             except Exception as e:
#                 raise UserError(_("เกิดข้อผิดพลาดในการแปลง JSON: %s") % str(e))
#
#             # ✅ ตรวจสอบ JSON ที่ได้รับ
#             if "error" in data:
#                 raise UserError(_("\n❌ API Error: %s") % data["error"])
#
#             # ✅ ดึงข้อมูลคำสั่งขาย
#             so_data = data
#             sol_data = data.get("sale_order_lines", [])
#
#             if not so_data:
#                 raise UserError(_("\n❌ ไม่พบข้อมูล SO"))
#
#             self.write({
#                 'destination': so_data['destination'],
#                 'shipping_cost': so_data['shipping_cost'],
#                 'distance_km': so_data['distance_km']
#             })
#
#             # ✅ ลบรายการสินค้าก่อนเพิ่มใหม่
#             if self.order_line:
#                 self.order_line.unlink()
#
#             for sol in sol_data:
#                 product = self.env['product.product'].search([('default_code', '=', sol['default_code'])], limit=1)
#                 if product:
#                     self.env['sale.order.line'].create({
#                         'order_id': self.id,
#                         'product_id': product.id,
#                         'name': product.name,
#                         'pfb_quantity': sol['quantity'],
#                         'second_uom_qty': sol['second_uom_qty']
#                     })
#                 else:
#                     raise UserError(_("\n❌ ไม่พบสินค้าในระบบ: %s") % sol['default_code'])
#
#         else:
#             raise UserError(_("เกิดข้อผิดพลาดจาก API: %s") % response.text)
#
#     @api.onchange('so_number')
#     def _onchange_so_number(self):
#         """ ทำให้ Odoo ตรวจจับค่าเมื่อเปลี่ยน `so_number` """
#         if self.so_number:
#             print(f"SO Number Changed: {self.so_number}")
#
#     def dictfetchall(self, cursor):
#         """ แปลงผลลัพธ์จาก cursor ให้เป็น dictionary """
#         columns = [desc[0] for desc in cursor.description]
#         return [dict(zip(columns, row)) for row in cursor.fetchall()]
#
#
#     def action_fetch_rental_data(self):
#         """ ดึงข้อมูลจากฐานข้อมูลที่เลือกโดยใช้ psycopg2 """
#         if not self.database_selection or not self.so_number:
#             raise UserError(_("กรุณาเลือก Database และกรอกเลข SO ก่อนดำเนินการ!"))
#
#         # print(f"🔍 ค้นหา SO Number: {self.so_number}")
#
#         db_name = self.database_selection
#         db_user = "odoo"
#         db_password = "odoo"
#         db_host = "159.65.10.105"
#         db_port = "51432"
#
#         # ทดสอบผ่าน localhost
#         # db_name = self.database_selection
#         # db_user = "odoo14"
#         # db_password = "odoo14"
#         # db_host = "localhost"
#         # db_port = "5432"
#
#         try:
#             # เชื่อมต่อไปยังฐานข้อมูลที่เลือก
#             connection = psycopg2.connect(
#                 dbname=db_name,
#                 user=db_user,
#                 password=db_password,
#                 host=db_host,
#                 port=db_port
#             )
#             connection.autocommit = False  # ป้องกันการบันทึกข้อมูลอัตโนมัติ
#
#             with connection.cursor() as cursor:
#                 #  ปรับ Query ให้ดึงข้อมูลตาม SO Number ที่เลือก
#                 query_so = """
#                     SELECT
#                         so.id,
#                         emp.name AS delivery_employee_name,
#                         lp.name AS license_plate_name,
#                         so.destination,
#                         so.shipping_cost,
#                         so.distance_km
#                     FROM sale_order so
#                     LEFT JOIN hr_employee emp ON so.delivery_employee_id = emp.id
#                     LEFT JOIN fleet_license_plate lp ON so.license_plate_id = lp.id
#                     WHERE so.name = %s;
#                 """
#                 cursor.execute(query_so, (self.so_number,))
#                 sale_order_data = self.dictfetchall(cursor)
#
#                 if not sale_order_data:
#                     raise UserError(_("\n❌ ไม่พบข้อมูล SO ที่ค้นหาในฐานข้อมูล %s") % db_name)
#
#                 #  ปรับ Query ให้ดึงข้อมูลสินค้าตาม SO Number
#                 query_sol = """
#                     SELECT sol.order_id, sol.product_id, sol.name, pt.default_code, sol.pfb_quantity, sol.second_uom_qty
#                     FROM sale_order_line sol
#                     LEFT JOIN product_product pp ON sol.product_id = pp.id
#                     LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
#                     WHERE sol.order_id IN (SELECT id FROM sale_order WHERE name = %s);
#                 """
#                 cursor.execute(query_sol, (self.so_number,))
#                 sale_order_line_data = self.dictfetchall(cursor)
#
#             # ปิดการเชื่อมต่อฐานข้อมูล
#             connection.close()
#
#             # print("\n=== ข้อมูลจาก Sale Order ===")
#             for so in sale_order_data:
#                 # print(
#                 #     f"พนักงานส่งของ: {so['delivery_employee_name']} | ป้ายทะเบียนรถ: {so['license_plate_name']} | ปลายทาง: {so['destination']} | ค่าขนส่ง: {so['shipping_cost']} | ระยะทาง (km): {so['distance_km']}"
#                 # )
#
#                 #  ค้นหา SO ในระบบ Odoo
#                 existing_so = self.env['sale.order'].search([('name', '=', self.so_number)], limit=1)
#
#                 #  ค้นหา ID ของพนักงาน
#                 employee = self.env['hr.employee'].search([('name', '=', so['delivery_employee_name'])], limit=1)
#                 if not employee:
#                     raise UserError(_("\n❌ ไม่พบพนักงาน: %s") % so['delivery_employee_name'])
#
#                 #  ค้นหา ID ของป้ายทะเบียน
#                 license_plate = self.env['fleet.license_plate'].search([('name', '=', so['license_plate_name'])],
#                                                                        limit=1)
#                 if not license_plate:
#                     raise UserError(_("\n❌ ไม่พบป้ายทะเบียน: %s") % so['license_plate_name'])
#
#                 if existing_so:
#                     #  Debug ค่าก่อนอัปเดต
#                     self.delivery_employee_id = employee.id
#                     self.license_plate_id = license_plate.id
#                     self.destination = so['destination']
#                     self.shipping_cost = so['shipping_cost']
#                     self.distance_km = so['distance_km']
#
#                 else:
#                     #  ถ้ายังไม่มี SO ให้สร้างใหม่
#                     existing_so = self.env['sale.order'].create({
#                         'name': self.so_number,
#                         'partner_id': self.partner_id.id,
#                         'delivery_employee_id': employee.id,
#                         'license_plate_id': license_plate.id,
#                         'destination': so['destination'],
#                         'shipping_cost': so['shipping_cost'],
#                         'distance_km': so['distance_km']
#                     })
#                     # print(f" สร้าง Sale Order ใหม่: {existing_so.name}")
#
#             #  ลบรายการสินค้าเก่า ก่อนเพิ่มใหม่
#             if self.order_line:
#                 self.order_line.unlink()
#
#             for sol in sale_order_line_data:
#                 default_code = sol['default_code'] if sol['default_code'] else ""  # ป้องกัน None
#                 if "]" in default_code:
#                     default_code = default_code.split('] ')[0].strip('[]')  # ตัดโค้ดออก
#
#                 product = self.env['product.product'].search([('default_code', '=', default_code)], limit=1)
#
#                 if not product:
#                     raise UserError(_("\n❌ ไม่พบสินค้าในระบบ Odoo: %s (เดิม: %s)") % (default_code, sol['name']))
#
#                 total_weight = sol['pfb_quantity'] * sol['second_uom_qty']
#
#                 self.env['sale.order.line'].create({
#                     'order_id': self.id,
#                     'product_id': product.id,
#                     'name': product.name,  # ใช้ชื่อสินค้าจาก Odoo
#                     'pfb_quantity': sol['pfb_quantity'],
#                     'second_uom_qty': sol['second_uom_qty'],
#                     'total_weight': total_weight
#                 })
#                 # print(f"➕ เพิ่มสินค้าใหม่: {product.name} | Quantity: {sol['pfb_quantity']}")
#
#         except Exception as e:
#             raise UserError(_("เกิดข้อผิดพลาดขณะเชื่อมต่อฐานข้อมูล API: %s") % str(e))
#
#         return True
#
#
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_renew_green_house_line = fields.Boolean(related='order_id.is_renew_green_house', string="บิลต่ออายุจากบ้านเขียว", readonly=True)
    total_weight = fields.Float(string="น้ำหนักรวม", compute="_compute_total_weight", store=True, readonly=False)
    pfb_quantity = fields.Integer(string="Quantity Rent", store=True)
    second_uom_qty = fields.Float('Secondary Qty')

    @api.depends('pfb_quantity', 'second_uom_qty', 'order_id.database_selection', 'order_id.so_number', 'order_id.is_renew_green_house')
    def _compute_total_weight(self):
        for line in self:
            order = line.order_id
            # ถ้าติ๊กบิลต่ออายุจากบ้านเขียว → ไม่ compute ให้กรอกเอง
            if order.is_renew_green_house:
                continue
            if (
                    line.pfb_quantity and line.second_uom_qty and
                    not order.database_selection and
                    not order.so_number
            ):
                line.total_weight = line.pfb_quantity * line.second_uom_qty
