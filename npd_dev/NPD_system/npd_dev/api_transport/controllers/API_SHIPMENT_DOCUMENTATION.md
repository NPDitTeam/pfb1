# 📚 API Documentation - Sale Order with Shipment Information

## 🎯 ภาพรวม
API นี้ใช้สำหรับดึงข้อมูล Sale Order พร้อมข้อมูลการขนส่งแบบครบถ้วน รวมถึงข้อมูลค่าน้ำมัน ค่าเสื่อมราคา ค่าแรงงาน และต้นทุนการขนส่งทั้งหมด

---

## 📡 Endpoints

### 1. GET Sale Orders (รายการหลายรายการ)
**Endpoint:** `/api/sale_orders`
**Method:** `POST`
**Type:** `JSON`
**Auth:** `user`

#### 📋 Parameters (Optional)
```json
{
  "order_ids": [1, 2, 3],           // รายการ ID ของ Sale Order
  "state": "sale",                   // สถานะ: 'draft', 'sent', 'sale', 'done', 'cancel'
  "date_from": "2025-01-01",         // วันที่เริ่มต้น (YYYY-MM-DD)
  "date_to": "2025-12-31",           // วันที่สิ้นสุด (YYYY-MM-DD)
  "partner_id": 123,                 // ID ของลูกค้า
  "limit": 100,                      // จำนวนรายการสูงสุด (default: 100)
  "offset": 0                        // เริ่มต้นจากรายการที่ (default: 0)
}
```

---

### 2. GET Sale Order Detail (รายการเดียว)
**Endpoint:** `/api/sale_order/<order_id>`
**Method:** `POST`
**Type:** `JSON`
**Auth:** `user`

#### 📋 Parameters
```json
{
  "order_id": 123  // ID ของ Sale Order ที่ต้องการ
}
```

---

## 📊 Response Structure

### ✅ Success Response
```json
{
  "success": true,
  "data": [
    {
      // ข้อมูลพื้นฐาน
      "id": 123,
      "name": "SO001",
      "branch_id": "สาขากรุงเทพ",
      "state": "sale",
      "state_text": "ขายแล้ว",
      "date_order": "2025-01-15 10:30:00",
      "validity_date": "2025-02-15",

      // ข้อมูลลูกค้า
      "partner_id": 456,
      "partner_name": "บริษัท ABC จำกัด",
      "partner_phone": "02-123-4567",
      "partner_email": "contact@abc.com",

      // 🚚 ข้อมูลการขนส่งแบบครบถ้วน
      "shipment_information": {
        
        // 🚚 ข้อมูลการขนส่งพื้นฐาน
        "basic": {
          "pickup_location": "คลังสินค้ากรุงเทพ",
          "destination": "สาขาเชียงใหม่",
          "vehicle_type_id": 10,
          "vehicle_type_name": "รถ 6 ล้อ",
          "distance_km": 689.50,
          "shipping_cost_raw": 12450.00,
          "shipping_cost": 12500.00,
          "shipping_cost_m": 500.00
        },

        // 👤 ข้อมูลพนักงานและรถ
        "vehicle_assignment": {
          "delivery_employee_id": 25,
          "delivery_employee_name": "นายสมชาย ใจดี",
          "license_plate_id": 8,
          "license_plate_name": "กข-1234 กรุงเทพ"
        },

        // ⛽ ข้อมูลค่าน้ำมัน
        "fuel": {
          "fuel_price_per_liter": 35.50,
          "fuel_consumption_rate": 8.5,
          "fuel_used_per_trip": 162.12,
          "fuel_cost_per_trip": 5755.26
        },

        // 📉 ข้อมูลค่าเสื่อมราคา
        "depreciation": {
          "vehicle": 1200000.00,
          "vehicle_cost": 1344000.00,
          "salvage_value": 120000.00,
          "depreciation_period": 10,
          "depreciation_per_trip": 45.00
        },

        // 💰 ค่าใช้จ่ายประจำปี
        "annual_expenses": {
          "annual_vehicle_tax_y": 8500.00,
          "annual_vehicle_tax": 8500.00,
          "annual_insurance_class2": 15000.00,
          "annual_insurance_class1": 15000.00,
          "annual_compulsory_insurance1": 600.00,
          "annual_compulsory_insurance": 600.00,
          "total_depreciation_per_trip": 78.50
        },

        // 👷 ข้อมูลค่าแรงงาน
        "labor": {
          "labor_costs": 18000,
          "working_days_per_month": 26,
          "driver_salary": 18000.00,
          "maintenance_cost": 3000.00,
          "trips_per_day": 2,
          "labor_cost_per_trip": 400.00,
          "total_labor_per_trip": 450.00
        },

        // 📋 ค่าใช้จ่ายอื่นๆ
        "other_expenses": {
          "other_expenses": 150.00
        },

        // 📊 สรุปต้นทุนและกำไร
        "cost_summary": {
          "total_cost_per_trip": 6433.76,
          "profit_per_trip": 6066.24,
          "profit_per_trip_p": 48.53
        }
      },

      // ข้อมูลการเงิน
      "amount_untaxed": 10000.00,
      "amount_tax": 700.00,
      "amount_total": 10700.00,
      "currency": "THB",

      // ข้อมูลเพิ่มเติม
      "user_id": 2,
      "salesperson_name": "นายพนักงานขาย",
      "company_id": 1,
      "company_name": "บริษัทหลัก",
      "note": "หมายเหตุพิเศษ",

      // รายการสินค้า
      "order_lines": [
        {
          "id": 789,
          "product_id": 50,
          "product_name": "สินค้า A",
          "product_code": "PROD-A-001",
          "description": "รายละเอียดสินค้า A",
          "quantity": 10.0,
          "uom": "ชิ้น",
          "price_unit": 1000.00,
          "discount": 0.0,
          "price_subtotal": 10000.00,
          "price_tax": 700.00,
          "price_total": 10700.00
        }
      ],
      "order_lines_count": 1
    }
  ],
  "count": 1,
  "total": 1,
  "message": "ดึงข้อมูลสำเร็จ 1 รายการจากทั้งหมด 1 รายการ"
}
```

### ❌ Error Response
```json
{
  "success": false,
  "data": [],
  "count": 0,
  "total": 0,
  "message": "เกิดข้อผิดพลาด: <error_message>"
}
```

---

## 🔍 รายละเอียดข้อมูล Shipment Information

### 🚚 Basic (ข้อมูลการขนส่งพื้นฐาน)
| Field | Type | Description |
|-------|------|-------------|
| `pickup_location` | String | จุดรับของ |
| `destination` | String | จุดส่งของ |
| `vehicle_type_id` | Integer | ID ประเภทรถ |
| `vehicle_type_name` | String | ชื่อประเภทรถ |
| `distance_km` | Float | ระยะทาง (กิโลเมตร) |
| `shipping_cost_raw` | Float | ค่าขนส่งก่อนปัดเศษ |
| `shipping_cost` | Float | ค่าขนส่งหลังปัดเศษ |
| `shipping_cost_m` | Float | ค่าขนส่งพิเศษ |

### 👤 Vehicle Assignment (ข้อมูลพนักงานและรถ)
| Field | Type | Description |
|-------|------|-------------|
| `delivery_employee_id` | Integer | ID พนักงานส่งของ |
| `delivery_employee_name` | String | ชื่อพนักงานส่งของ |
| `license_plate_id` | Integer | ID ป้ายทะเบียนรถ |
| `license_plate_name` | String | ป้ายทะเบียนรถ |

### ⛽ Fuel (ข้อมูลค่าน้ำมัน)
| Field | Type | Description |
|-------|------|-------------|
| `fuel_price_per_liter` | Float | ค่าน้ำมันเชื้อเพลิง (บาท/ลิตร) |
| `fuel_consumption_rate` | Float | อัตราสิ้นเปลืองเชื้อเพลิง (กม./ลิตร) |
| `fuel_used_per_trip` | Float | จำนวนน้ำมันที่ใช้ต่อการเดินทางไป-กลับ (ลิตร) |
| `fuel_cost_per_trip` | Float | ค่าน้ำมันเที่ยวไปกลับรอบนี้ (บาท) |

### 📉 Depreciation (ข้อมูลค่าเสื่อมราคา)
| Field | Type | Description |
|-------|------|-------------|
| `vehicle` | Float | ต้นทุนค่ารถ |
| `vehicle_cost` | Float | ต้นทุนค่ารถดอกเบี้ย ร้อยละ 12 บ./ปี (บาท) |
| `salvage_value` | Float | มูลค่าซาก (บาท) |
| `depreciation_period` | Integer | ระยะเวลาค่าเสื่อมราคา (ปี) |
| `depreciation_per_trip` | Float | ค่าเสื่อมตัวรถต่อรอบ (บาท) |

### 💰 Annual Expenses (ค่าใช้จ่ายประจำปี)
| Field | Type | Description |
|-------|------|-------------|
| `annual_vehicle_tax_y` | Float | ค่าภาษีป้ายวงกลม (บาท/ปี) |
| `annual_vehicle_tax` | Float | ค่าภาษีป้ายวงกลม (บาท/ปี) |
| `annual_insurance_class2` | Float | ค่าเบี้ยประกันชั้น |
| `annual_insurance_class1` | Float | ประกันชั้น 1 รถยนต์ (บาท/ปี) |
| `annual_compulsory_insurance1` | Float | ค่าประกัน พรบ |
| `annual_compulsory_insurance` | Float | ค่าประกัน พรบ. (บาท/ปี) |
| `total_depreciation_per_trip` | Float | รวมค่าเสื่อมต่างๆต่อรอบไปกลับ (บาท) |

### 👷 Labor (ข้อมูลค่าแรงงาน)
| Field | Type | Description |
|-------|------|-------------|
| `labor_costs` | Integer | ค่าแรง |
| `working_days_per_month` | Integer | จำนวนวันทำงานต่อเดือน |
| `driver_salary` | Float | เงินเดือน (บาท/เดือน) |
| `maintenance_cost` | Float | ค่าซ่อมบำรุง (บาท/เดือน) |
| `trips_per_day` | Integer | จำนวนรอบที่วิ่ง/วัน |
| `labor_cost_per_trip` | Float | คิดค่าแรงให้ พนง.ขับรถต่อเที่ยว (บาท) |
| `total_labor_per_trip` | Float | ค่าแรงต่อรอบไปกลับ (บาท) |

### 📋 Other Expenses (ค่าใช้จ่ายอื่นๆ)
| Field | Type | Description |
|-------|------|-------------|
| `other_expenses` | Float | ค่าใช้จ่ายอื่นๆเช่น ค่าโทรศัพท์ ค่าเอกสาร (บาท/รอบ) |

### 📊 Cost Summary (สรุปต้นทุนและกำไร)
| Field | Type | Description |
|-------|------|-------------|
| `total_cost_per_trip` | Float | ราคาต้นทุน (บาท/รอบ) |
| `profit_per_trip` | Float | กำไร (บาท/รอบ) |
| `profit_per_trip_p` | Float | กำไร% (บาท/รอบ) |

---

## 💡 ตัวอย่างการเรียกใช้งาน

### Python Example
```python
import requests
import json

# Configuration
url = "http://your-odoo-server.com/api/sale_orders"
headers = {
    "Content-Type": "application/json"
}

# Session/Cookie authentication
session = requests.Session()
session.cookies.set('session_id', 'your-session-id')

# Request payload
payload = {
    "state": "sale",
    "date_from": "2025-01-01",
    "date_to": "2025-12-31",
    "limit": 50,
    "offset": 0
}

# Make request
response = session.post(url, json=payload, headers=headers)
data = response.json()

if data['success']:
    print(f"Found {data['count']} orders")
    for order in data['data']:
        print(f"Order: {order['name']}")
        print(f"Shipping Cost: {order['shipment_information']['basic']['shipping_cost']}")
        print(f"Total Cost: {order['shipment_information']['cost_summary']['total_cost_per_trip']}")
        print(f"Profit: {order['shipment_information']['cost_summary']['profit_per_trip']}")
        print("---")
else:
    print(f"Error: {data['message']}")
```

### JavaScript Example
```javascript
// Using Fetch API
const url = 'http://your-odoo-server.com/api/sale_orders';

const payload = {
  state: 'sale',
  date_from: '2025-01-01',
  date_to: '2025-12-31',
  limit: 50,
  offset: 0
};

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  credentials: 'include', // Include cookies
  body: JSON.stringify(payload)
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    console.log(`Found ${data.count} orders`);
    data.data.forEach(order => {
      console.log(`Order: ${order.name}`);
      console.log(`Shipping Cost: ${order.shipment_information.basic.shipping_cost}`);
      console.log(`Total Cost: ${order.shipment_information.cost_summary.total_cost_per_trip}`);
      console.log(`Profit: ${order.shipment_information.cost_summary.profit_per_trip}`);
      console.log('---');
    });
  } else {
    console.error(`Error: ${data.message}`);
  }
})
.catch(error => console.error('Error:', error));
```

### cURL Example
```bash
curl -X POST \
  'http://your-odoo-server.com/api/sale_orders' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: session_id=your-session-id' \
  -d '{
    "state": "sale",
    "date_from": "2025-01-01",
    "date_to": "2025-12-31",
    "limit": 50,
    "offset": 0
  }'
```

---

## 🔐 Authentication

API นี้ใช้ `auth='user'` ซึ่งหมายความว่าต้อง authenticate ผ่าน Odoo session:

1. **Web Interface:** ใช้ session cookie จาก browser
2. **API Client:** ต้อง login ผ่าน `/web/session/authenticate` ก่อน
3. **External System:** แนะนำให้สร้าง API Key หรือใช้ OAuth

---

## ⚠️ หมายเหตุสำคัญ

1. ข้อมูล Shipment Information จะมีค่าเป็น `null` หากไม่ได้กรอกข้อมูลในฟิลด์นั้น
2. การคำนวณต้นทุนและกำไรจะทำอัตโนมัติผ่าน computed fields ใน Odoo
3. แนะนำให้ใช้ `limit` และ `offset` สำหรับ pagination เมื่อมีข้อมูลจำนวนมาก
4. รองรับการค้นหาด้วยหลายเงื่อนไขพร้อมกัน (AND logic)
5. วันที่ต้องอยู่ในรูปแบบ YYYY-MM-DD

---

## 📞 Support

หากมีปัญหาหรือข้อสงสัยเพิ่มเติม กรุณาติดต่อทีมพัฒนาระบบ

**Version:** 1.0.0  
**Last Updated:** October 2025  
**Module:** api_transport
