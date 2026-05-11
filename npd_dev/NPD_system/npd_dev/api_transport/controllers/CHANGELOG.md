# 📝 สรุปการเพิ่มข้อมูล ShipmentInformation ใน API

## 📅 วันที่: October 2025
## 👤 ผู้พัฒนา: System Developer
## 📦 Module: api_transport

---

## 🎯 วัตถุประสงค์

เพิ่มข้อมูล ShipmentInformation ทั้งหมดจาก model ให้สามารถเรียกดูผ่าน API ได้แบบครบถ้วน รวมถึง:
- ข้อมูลการขนส่งพื้นฐาน
- ข้อมูลค่าน้ำมัน
- ข้อมูลค่าเสื่อมราคา
- ค่าใช้จ่ายประจำปี
- ค่าแรงงาน
- สรุปต้นทุนและกำไร

---

## 📂 ไฟล์ที่มีการเปลี่ยนแปลง

### 1. ✏️ แก้ไข: `sale_order_api.py`

#### เพิ่ม Function ใหม่:
```python
def _get_shipment_info(self, order):
    """
    ฟังก์ชันสำหรับดึงข้อมูล ShipmentInformation แบบครบถ้วน
    จัดกลุ่มข้อมูลเป็น 8 หมวดหมู่:
    - basic: ข้อมูลพื้นฐาน
    - vehicle_assignment: พนักงานและรถ
    - fuel: ข้อมูลน้ำมัน
    - depreciation: ค่าเสื่อมราคา
    - annual_expenses: ค่าใช้จ่ายประจำปี
    - labor: ค่าแรงงาน
    - other_expenses: ค่าใช้จ่ายอื่นๆ
    - cost_summary: สรุปต้นทุนและกำไร
    """
```

#### แก้ไข Endpoints:
1. **`/api/sale_orders`** - เปลี่ยนจาก return ข้อมูลขนส่งพื้นฐานเป็น `shipment_information` object แบบครบถ้วน
2. **`/api/sale_order/<order_id>`** - เปลี่ยนเช่นเดียวกัน

---

## 📊 โครงสร้างข้อมูลที่เพิ่มใหม่

### ก่อนแก้ไข (Old Structure):
```json
{
  "pickup_location": "...",
  "destination": "...",
  "vehicle_type_id": 10,
  "distance_km": 100,
  "shipping_cost": 5000,
  "delivery_employee_id": 5,
  "license_plate_id": 8
}
```

### หลังแก้ไข (New Structure):
```json
{
  "shipment_information": {
    "basic": {
      "pickup_location": "...",
      "destination": "...",
      "vehicle_type_id": 10,
      "distance_km": 100,
      "shipping_cost_raw": 4950,
      "shipping_cost": 5000,
      "shipping_cost_m": 500
    },
    "vehicle_assignment": {
      "delivery_employee_id": 5,
      "delivery_employee_name": "...",
      "license_plate_id": 8,
      "license_plate_name": "..."
    },
    "fuel": {
      "fuel_price_per_liter": 35.5,
      "fuel_consumption_rate": 8.5,
      "fuel_used_per_trip": 162.12,
      "fuel_cost_per_trip": 5755.26
    },
    "depreciation": { ... },
    "annual_expenses": { ... },
    "labor": { ... },
    "other_expenses": { ... },
    "cost_summary": {
      "total_cost_per_trip": 6433.76,
      "profit_per_trip": 6066.24,
      "profit_per_trip_p": 48.53
    }
  }
}
```

---

## 📋 ฟิลด์ที่เพิ่มเข้ามาใหม่ (Total: 33 fields)

### 🚚 Basic (8 fields)
- [NEW] `shipping_cost_m` - ค่าขนส่งพิเศษ
- [EXISTING] pickup_location, destination, vehicle_type_id, vehicle_type_name, distance_km, shipping_cost_raw, shipping_cost

### ⛽ Fuel (4 fields) - ทั้งหมดเป็น NEW
- `fuel_price_per_liter` - ค่าน้ำมันเชื้อเพลิง (บาท/ลิตร)
- `fuel_consumption_rate` - อัตราสิ้นเปลืองเชื้อเพลิง (กม./ลิตร)
- `fuel_used_per_trip` - จำนวนน้ำมันที่ใช้ต่อเที่ยว (ลิตร)
- `fuel_cost_per_trip` - ค่าน้ำมันต่อเที่ยว (บาท)

### 📉 Depreciation (5 fields) - ทั้งหมดเป็น NEW
- `vehicle` - ต้นทุนค่ารถ
- `vehicle_cost` - ต้นทุนค่ารถดอกเบี้ย ร้อยละ 12 บ./ปี
- `salvage_value` - มูลค่าซาก
- `depreciation_period` - ระยะเวลาค่าเสื่อมราคา (ปี)
- `depreciation_per_trip` - ค่าเสื่อมตัวรถต่อรอบ

### 💰 Annual Expenses (7 fields) - ทั้งหมดเป็น NEW
- `annual_vehicle_tax_y` - ค่าภาษีป้ายวงกลม (บาท/ปี)
- `annual_vehicle_tax` - ค่าภาษีป้ายวงกลม (computed)
- `annual_insurance_class2` - ค่าเบี้ยประกันชั้น
- `annual_insurance_class1` - ประกันชั้น 1 (computed)
- `annual_compulsory_insurance1` - ค่าประกัน พรบ
- `annual_compulsory_insurance` - ค่าประกัน พรบ. (computed)
- `total_depreciation_per_trip` - รวมค่าเสื่อมต่อรอบ

### 👷 Labor (7 fields) - ทั้งหมดเป็น NEW
- `labor_costs` - ค่าแรง
- `working_days_per_month` - จำนวนวันทำงานต่อเดือน
- `driver_salary` - เงินเดือน (บาท/เดือน)
- `maintenance_cost` - ค่าซ่อมบำรุง (บาท/เดือน)
- `trips_per_day` - จำนวนรอบที่วิ่ง/วัน
- `labor_cost_per_trip` - ค่าแรงต่อเที่ยว
- `total_labor_per_trip` - ค่าแรงต่อรอบไปกลับ

### 📋 Other Expenses (1 field) - NEW
- `other_expenses` - ค่าใช้จ่ายอื่นๆ (บาท/รอบ)

### 📊 Cost Summary (3 fields) - ทั้งหมดเป็น NEW
- `total_cost_per_trip` - ราคาต้นทุน (บาท/รอบ)
- `profit_per_trip` - กำไร (บาท/รอบ)
- `profit_per_trip_p` - กำไร% (บาท/รอบ)

---

## 📄 ไฟล์เอกสารที่สร้างใหม่

### 1. 📘 `API_SHIPMENT_DOCUMENTATION.md`
- เอกสาร API อย่างละเอียด
- ตัวอย่าง Response Structure
- ตารางรายละเอียดฟิลด์ทั้งหมด
- ตัวอย่างการเรียกใช้งานด้วย Python, JavaScript, และ cURL
- คำอธิบาย Authentication
- หมายเหตุสำคัญ

### 2. 🧪 `test_api.py`
- ไฟล์ทดสอบ API
- Class `OdooAPITester` สำหรับจัดการ connection
- Function `test_basic_functionality()` - ทดสอบการทำงานพื้นฐาน
- Function `test_shipment_data_completeness()` - ทดสอบความครบถ้วนของข้อมูล
- แสดงผลแบบ pretty-print พร้อม emoji

---

## ✅ การทดสอบ

### ขั้นตอนการทดสอบ:

1. **Restart Odoo Service**
   ```bash
   # Windows
   net stop odoo
   net start odoo
   ```

2. **ทดสอบด้วย Python Script**
   ```bash
   cd C:\Program Files\Odoo 14.0.20231205\server\odoo\custom\pfb1\npd_dev\NPD_system\npd_dev\api_transport\controllers
   python test_api.py
   ```

3. **ทดสอบด้วย cURL**
   ```bash
   curl -X POST http://localhost:8069/api/sale_orders \
     -H "Content-Type: application/json" \
     -H "Cookie: session_id=your-session-id" \
     -d '{"limit": 5}'
   ```

---

## 🔍 การตรวจสอบ

### ตรวจสอบว่า API ทำงานถูกต้อง:

1. ✅ Response มี key `shipment_information`
2. ✅ `shipment_information` มี 8 หมวดหมู่ย่อย
3. ✅ แต่ละหมวดหมู่มีฟิลด์ครบตามที่กำหนด
4. ✅ ฟิลด์ computed (เช่น `fuel_cost_per_trip`) มีการคำนวณถูกต้อง
5. ✅ ฟิลด์ที่เป็น `null` แสดงว่าไม่มีข้อมูลในฐานข้อมูล

---

## 🎁 ประโยชน์ที่ได้รับ

1. **ครบถ้วน**: สามารถเรียกดูข้อมูลต้นทุนและกำไรได้ทั้งหมดผ่าน API
2. **จัดกลุ่มชัดเจน**: แบ่งข้อมูลเป็นหมวดหมู่ เข้าใจง่าย
3. **ใช้งานสะดวก**: มี function helper `_get_shipment_info()` ที่สามารถนำไปใช้ในที่อื่นได้
4. **มีเอกสาร**: มีเอกสารอธิบายและตัวอย่างการใช้งานครบถ้วน
5. **ทดสอบง่าย**: มีไฟล์ test พร้อมใช้งาน

---

## 🚀 การใช้งานต่อ

### Integration กับระบบอื่น:
1. Dashboard แสดงรายงานต้นทุน
2. Mobile App สำหรับพนักงานส่งของ
3. ระบบวิเคราะห์กำไร/ขาดทุน
4. Export ข้อมูลเพื่อทำรายงาน Excel
5. Integration กับระบบบัญชี

---

## 📞 การติดต่อ

หากมีปัญหาหรือข้อสงสัย:
- ตรวจสอบ log ที่ Odoo server
- ดูเอกสารใน `API_SHIPMENT_DOCUMENTATION.md`
- ทดสอบด้วย `test_api.py`

---

## 📌 หมายเหตุ

- ⚠️ ข้อมูล shipment information จะมีค่าเป็น `null` หากไม่ได้กรอกข้อมูลใน Sale Order
- ⚠️ ฟิลด์ computed จะคำนวณอัตโนมัติจาก Odoo model
- ⚠️ แนะนำให้ทดสอบกับข้อมูลจริงเพื่อตรวจสอบความถูกต้อง
- ✅ API รองรับ pagination ด้วย `limit` และ `offset`
- ✅ สามารถ filter ด้วยหลายเงื่อนไขพร้อมกัน

---

**Version:** 1.0.0  
**Last Updated:** October 20, 2025  
**Status:** ✅ Ready for Production
