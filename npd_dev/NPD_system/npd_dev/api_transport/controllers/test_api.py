# -*- coding: utf-8 -*-
"""
🧪 ไฟล์ทดสอบ API Sale Order with Shipment Information

ไฟล์นี้ใช้สำหรับทดสอบการเรียกใช้ API โดยมีตัวอย่างทั้งหมดที่จำเป็น
"""

import requests
import json
from datetime import datetime, timedelta


class OdooAPITester:
    def __init__(self, base_url, db, username, password):
        """
        Initial connection to Odoo
        
        Args:
            base_url: URL ของ Odoo server (เช่น http://localhost:8069)
            db: ชื่อ database
            username: username ผู้ใช้
            password: รหัสผ่าน
        """
        self.base_url = base_url.rstrip('/')
        self.db = db
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session_id = None
        
    def login(self):
        """
        เข้าสู่ระบบ Odoo และรับ session_id
        """
        url = f"{self.base_url}/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password
            }
        }
        
        response = self.session.post(url, json=payload)
        result = response.json()
        
        if result.get('result') and result['result'].get('uid'):
            self.session_id = self.session.cookies.get('session_id')
            print(f"✅ Login successful! Session ID: {self.session_id}")
            return True
        else:
            print(f"❌ Login failed: {result.get('error', {}).get('message', 'Unknown error')}")
            return False
    
    def get_sale_orders(self, **kwargs):
        """
        ดึงข้อมูล Sale Orders พร้อมข้อมูลการขนส่ง
        
        Parameters:
            order_ids: [1,2,3] - รายการ ID ของ Sale Order
            state: 'draft', 'sent', 'sale', 'done', 'cancel'
            date_from: '2025-01-01' - วันที่เริ่มต้น
            date_to: '2025-12-31' - วันที่สิ้นสุด
            partner_id: 123 - ID ของลูกค้า
            limit: 100 - จำนวนรายการสูงสุด
            offset: 0 - เริ่มต้นจากรายการที่
        """
        url = f"{self.base_url}/api/sale_orders"
        payload = {
            "jsonrpc": "2.0",
            "params": kwargs
        }
        
        response = self.session.post(url, json=payload)
        return response.json()
    
    def get_sale_order_detail(self, order_id):
        """
        ดึงข้อมูล Sale Order รายการเดียว
        
        Parameters:
            order_id: ID ของ Sale Order
        """
        url = f"{self.base_url}/api/sale_order/{order_id}"
        payload = {
            "jsonrpc": "2.0",
            "params": {}
        }
        
        response = self.session.post(url, json=payload)
        return response.json()
    
    def print_shipment_summary(self, order):
        """
        แสดงสรุปข้อมูลการขนส่งแบบสวยงาม
        """
        print("\n" + "="*60)
        print(f"📋 Order: {order['name']}")
        print(f"👤 Customer: {order['partner_name']}")
        print("="*60)
        
        shipment = order.get('shipment_information', {})
        
        # Basic Info
        basic = shipment.get('basic', {})
        if basic.get('pickup_location') or basic.get('destination'):
            print("\n🚚 ข้อมูลการขนส่ง:")
            print(f"   จุดรับ: {basic.get('pickup_location', 'N/A')}")
            print(f"   จุดส่ง: {basic.get('destination', 'N/A')}")
            print(f"   ระยะทาง: {basic.get('distance_km', 0):.2f} กม.")
            print(f"   ค่าขนส่ง: {basic.get('shipping_cost', 0):,.2f} บาท")
        
        # Vehicle Assignment
        vehicle = shipment.get('vehicle_assignment', {})
        if vehicle.get('delivery_employee_name'):
            print("\n👤 พนักงานและรถ:")
            print(f"   พนักงานส่งของ: {vehicle.get('delivery_employee_name', 'N/A')}")
            print(f"   ทะเบียนรถ: {vehicle.get('license_plate_name', 'N/A')}")
        
        # Fuel
        fuel = shipment.get('fuel', {})
        if fuel.get('fuel_cost_per_trip'):
            print("\n⛽ ข้อมูลน้ำมัน:")
            print(f"   ราคาน้ำมัน: {fuel.get('fuel_price_per_liter', 0):.2f} บาท/ลิตร")
            print(f"   อัตราสิ้นเปลือง: {fuel.get('fuel_consumption_rate', 0):.2f} กม./ลิตร")
            print(f"   น้ำมันที่ใช้: {fuel.get('fuel_used_per_trip', 0):.2f} ลิตร")
            print(f"   ค่าน้ำมันรวม: {fuel.get('fuel_cost_per_trip', 0):,.2f} บาท")
        
        # Cost Summary
        cost = shipment.get('cost_summary', {})
        if cost.get('total_cost_per_trip'):
            print("\n📊 สรุปต้นทุนและกำไร:")
            print(f"   ต้นทุนรวม: {cost.get('total_cost_per_trip', 0):,.2f} บาท")
            print(f"   กำไร: {cost.get('profit_per_trip', 0):,.2f} บาท")
            print(f"   เปอร์เซ็นต์กำไร: {cost.get('profit_per_trip_p', 0):.2f}%")
        
        print("="*60)


def test_basic_functionality():
    """
    🧪 ทดสอบการทำงานพื้นฐาน
    """
    print("\n" + "="*60)
    print("🧪 เริ่มการทดสอบ API")
    print("="*60)
    
    # Configuration - แก้ไขตามของคุณ
    tester = OdooAPITester(
        base_url="http://localhost:8069",
        db="your_database_name",
        username="admin",
        password="admin"
    )
    
    # 1. Login
    print("\n1️⃣ กำลังเข้าสู่ระบบ...")
    if not tester.login():
        print("❌ การทดสอบหยุดเนื่องจาก login ไม่สำเร็จ")
        return
    
    # 2. ทดสอบดึง Sale Orders ทั้งหมด
    print("\n2️⃣ ทดสอบดึง Sale Orders ทั้งหมด (limit 5)...")
    result = tester.get_sale_orders(limit=5)
    
    if result.get('result', {}).get('success'):
        data = result['result']
        print(f"✅ พบ {data['count']} รายการจากทั้งหมด {data['total']} รายการ")
        
        # แสดงสรุปแต่ละรายการ
        for order in data['data']:
            tester.print_shipment_summary(order)
    else:
        print(f"❌ Error: {result.get('result', {}).get('message', 'Unknown error')}")
    
    # 3. ทดสอบดึง Sale Order รายการเดียว (ถ้ามีข้อมูล)
    if result.get('result', {}).get('data') and len(result['result']['data']) > 0:
        first_order_id = result['result']['data'][0]['id']
        print(f"\n3️⃣ ทดสอบดึง Sale Order รายการเดียว (ID: {first_order_id})...")
        
        detail_result = tester.get_sale_order_detail(first_order_id)
        if detail_result.get('result', {}).get('success'):
            print("✅ ดึงข้อมูลสำเร็จ")
            tester.print_shipment_summary(detail_result['result']['data'])
        else:
            print(f"❌ Error: {detail_result.get('result', {}).get('message', 'Unknown error')}")
    
    # 4. ทดสอบ filter ตามสถานะ
    print("\n4️⃣ ทดสอบ filter ตาม state='sale'...")
    result = tester.get_sale_orders(state='sale', limit=3)
    if result.get('result', {}).get('success'):
        data = result['result']
        print(f"✅ พบ {data['count']} รายการที่มีสถานะ 'sale'")
    else:
        print(f"❌ Error: {result.get('result', {}).get('message', 'Unknown error')}")
    
    # 5. ทดสอบ filter ตามวันที่
    print("\n5️⃣ ทดสอบ filter ตามวันที่ (30 วันที่ผ่านมา)...")
    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    date_to = datetime.now().strftime('%Y-%m-%d')
    
    result = tester.get_sale_orders(
        date_from=date_from,
        date_to=date_to,
        limit=3
    )
    if result.get('result', {}).get('success'):
        data = result['result']
        print(f"✅ พบ {data['count']} รายการระหว่าง {date_from} ถึง {date_to}")
    else:
        print(f"❌ Error: {result.get('result', {}).get('message', 'Unknown error')}")
    
    print("\n" + "="*60)
    print("✅ การทดสอบเสร็จสิ้น")
    print("="*60)


def test_shipment_data_completeness():
    """
    🧪 ทดสอบความครบถ้วนของข้อมูล Shipment
    """
    print("\n" + "="*60)
    print("🧪 ทดสอบความครบถ้วนของข้อมูล Shipment Information")
    print("="*60)
    
    # Configuration
    tester = OdooAPITester(
        base_url="http://localhost:8069",
        db="your_database_name",
        username="admin",
        password="admin"
    )
    
    # Login
    if not tester.login():
        return
    
    # ดึงข้อมูล
    result = tester.get_sale_orders(limit=1)
    
    if not result.get('result', {}).get('success'):
        print("❌ ไม่สามารถดึงข้อมูลได้")
        return
    
    orders = result['result']['data']
    if not orders:
        print("❌ ไม่พบข้อมูล Sale Order")
        return
    
    order = orders[0]
    shipment = order.get('shipment_information', {})
    
    # ตรวจสอบความครบถ้วนของแต่ละหมวด
    categories = {
        'basic': '🚚 ข้อมูลพื้นฐาน',
        'vehicle_assignment': '👤 พนักงานและรถ',
        'fuel': '⛽ ข้อมูลน้ำมัน',
        'depreciation': '📉 ค่าเสื่อมราคา',
        'annual_expenses': '💰 ค่าใช้จ่ายประจำปี',
        'labor': '👷 ค่าแรงงาน',
        'other_expenses': '📋 ค่าใช้จ่ายอื่นๆ',
        'cost_summary': '📊 สรุปต้นทุนและกำไร'
    }
    
    print(f"\n📋 Order: {order['name']}")
    print("="*60)
    
    for category_key, category_name in categories.items():
        category_data = shipment.get(category_key, {})
        
        if not category_data:
            print(f"\n{category_name}: ❌ ไม่พบข้อมูล")
            continue
        
        # นับจำนวนฟิลด์ที่มีค่า vs ทั้งหมด
        total_fields = len(category_data)
        filled_fields = sum(1 for v in category_data.values() if v is not None)
        
        percentage = (filled_fields / total_fields * 100) if total_fields > 0 else 0
        
        print(f"\n{category_name}:")
        print(f"   ฟิลด์ที่มีข้อมูล: {filled_fields}/{total_fields} ({percentage:.1f}%)")
        
        # แสดงฟิลด์ที่มีค่า
        for field, value in category_data.items():
            if value is not None:
                if isinstance(value, float):
                    print(f"   ✅ {field}: {value:,.2f}")
                else:
                    print(f"   ✅ {field}: {value}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    print("""
    
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║        🧪 Odoo Sale Order API Tester                      ║
║        with Shipment Information                           ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝

เลือกการทดสอบ:
1. ทดสอบการทำงานพื้นฐาน (Basic Functionality Test)
2. ทดสอบความครบถ้วนของข้อมูล (Data Completeness Test)
3. ทดสอบทั้งหมด (Run All Tests)
    """)
    
    choice = input("กรุณาเลือก (1-3): ").strip()
    
    if choice == "1":
        test_basic_functionality()
    elif choice == "2":
        test_shipment_data_completeness()
    elif choice == "3":
        test_basic_functionality()
        test_shipment_data_completeness()
    else:
        print("❌ ตัวเลือกไม่ถูกต้อง")
