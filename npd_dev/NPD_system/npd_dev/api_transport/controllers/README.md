# 🚀 Sale Order API with Shipment Information

## 📖 ภาพรวม

โปรเจกต์นี้เพิ่มฟีเจอร์การดึงข้อมูล ShipmentInformation ทั้งหมดผ่าน API รวมถึงข้อมูลต้นทุน ค่าแรงงาน ค่าน้ำมัน และกำไรการขนส่ง

---

## 📂 โครงสร้างไฟล์

```
api_transport/controllers/
├── sale_order_api.py              # ✏️ Main API Controller (แก้ไขแล้ว)
├── API_SHIPMENT_DOCUMENTATION.md  # 📘 เอกสารการใช้งาน API
├── test_api.py                    # 🧪 ไฟล์ทดสอบ
├── CHANGELOG.md                   # 📝 สรุปการเปลี่ยนแปลง
└── README.md                      # 📖 ไฟล์นี้
```

---

## 🎯 ฟีเจอร์ที่เพิ่ม

✅ ข้อมูลการขนส่งพื้นฐาน (จุดรับ-ส่ง, ระยะทาง, ค่าขนส่ง)  
✅ ข้อมูลพนักงานและรถ (พนักงานส่งของ, ป้ายทะเบียน)  
✅ ข้อมูลค่าน้ำมัน (ราคา, อัตราสิ้นเปลือง, ค่าน้ำมันรวม)  
✅ ข้อมูลค่าเสื่อมราคา (ต้นทุนรถ, มูลค่าซาก, ค่าเสื่อม)  
✅ ค่าใช้จ่ายประจำปี (ภาษี, ประกัน, พรบ.)  
✅ ค่าแรงงาน (เงินเดือน, ค่าซ่อมบำรุง, ค่าแรงต่อเที่ยว)  
✅ ค่าใช้จ่ายอื่นๆ (โทรศัพท์, เอกสาร)  
✅ สรุปต้นทุนและกำไร (ต้นทุนรวม, กำไร, %กำไร)  

---

## 🚀 Quick Start

### 1. Restart Odoo
```bash
# Windows
net stop odoo
net start odoo

# Linux
sudo service odoo restart
```

### 2. ทดสอบ API
```bash
cd C:\Program Files\Odoo 14.0.20231205\server\odoo\custom\pfb1\npd_dev\NPD_system\npd_dev\api_transport\controllers
python test_api.py
```

### 3. เรียกใช้งาน API
```python
import requests

# Login
session = requests.Session()
# ... (ดูเพิ่มเติมใน test_api.py)

# Get Sale Orders
response = session.post(
    'http://localhost:8069/api/sale_orders',
    json={'limit': 10}
)
print(response.json())
```

---

## 📘 เอกสาร

- **API Documentation**: `API_SHIPMENT_DOCUMENTATION.md`  
  เอกสารการใช้งาน API อย่างละเอียด พร้อมตัวอย่างและตารางรายละเอียดฟิลด์

- **Changelog**: `CHANGELOG.md`  
  สรุปการเปลี่ยนแปลงและฟิลด์ที่เพิ่มเข้ามา

- **Test Script**: `test_api.py`  
  ไฟล์ Python สำหรับทดสอบ API

---

## 🔌 API Endpoints

### 1. GET Sale Orders (List)
```
POST /api/sale_orders
```
**Parameters:** order_ids, state, date_from, date_to, partner_id, limit, offset

### 2. GET Sale Order (Detail)
```
POST /api/sale_order/<order_id>
```
**Parameters:** order_id

---

## 📊 ตัวอย่าง Response

```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "name": "SO001",
      "shipment_information": {
        "basic": {
          "pickup_location": "คลังกรุงเทพ",
          "destination": "สาขาเชียงใหม่",
          "distance_km": 689.50,
          "shipping_cost": 12500.00
        },
        "fuel": {
          "fuel_cost_per_trip": 5755.26
        },
        "cost_summary": {
          "total_cost_per_trip": 6433.76,
          "profit_per_trip": 6066.24,
          "profit_per_trip_p": 48.53
        }
      }
    }
  ]
}
```

---

## 🧪 การทดสอบ

### เปิดไฟล์ test_api.py และแก้ไข configuration:
```python
tester = OdooAPITester(
    base_url="http://localhost:8069",      # แก้ตาม server
    db="your_database_name",               # แก้ตาม database
    username="admin",                      # แก้ตาม username
    password="admin"                       # แก้ตาม password
)
```

### รันการทดสอบ:
```bash
python test_api.py
```

เลือกการทดสอบ:
1. ทดสอบการทำงานพื้นฐาน
2. ทดสอบความครบถ้วนของข้อมูล
3. ทดสอบทั้งหมด

---

## ⚙️ Configuration

API ใช้ authentication แบบ `auth='user'` ซึ่งต้อง:
1. Login ผ่าน `/web/session/authenticate` ก่อน
2. ใช้ session cookie ในการเรียก API
3. หรือใช้ API Key (ถ้ามีการติดตั้ง)

---

## 🔍 Troubleshooting

### ❌ Error: ไม่สามารถดึงข้อมูลได้
- ตรวจสอบว่า Odoo service running อยู่
- ตรวจสอบ database name และ credentials
- ดู log ที่ Odoo server

### ❌ Error: shipment_information เป็น null
- ตรวจสอบว่า Sale Order มีข้อมูล ShipmentInformation
- ตรวจสอบว่า model ShipmentInformation ถูก install แล้ว

### ❌ Error: ฟิลด์บางตัวเป็น null
- ฟิลด์ที่เป็น computed อาจยังไม่ได้คำนวณ
- ตรวจสอบว่า related fields มีข้อมูลต้นทาง

---

## 📌 หมายเหตุสำคัญ

⚠️ **ข้อมูลที่เป็น null**  
ฟิลด์จะเป็น `null` ถ้าไม่มีการกรอกข้อมูลใน Sale Order

⚠️ **Computed Fields**  
ฟิลด์บางตัว (เช่น `fuel_cost_per_trip`, `profit_per_trip`) จะคำนวณอัตโนมัติจาก Odoo

✅ **Pagination**  
แนะนำให้ใช้ `limit` และ `offset` เมื่อดึงข้อมูลจำนวนมาก

✅ **Filtering**  
สามารถใช้หลายเงื่อนไขพร้อมกัน (AND logic)

---

## 🎯 Use Cases

### 1. Dashboard แสดงต้นทุน
ดึงข้อมูลต้นทุนและกำไรเพื่อแสดงบน dashboard

### 2. Mobile App พนักงานส่งของ
ดึงข้อมูลการส่งของพร้อมรายละเอียดเส้นทาง

### 3. รายงานวิเคราะห์
Export ข้อมูลเพื่อทำรายงาน Excel หรือ PDF

### 4. Integration กับระบบบัญชี
ส่งข้อมูลต้นทุนไปยังระบบบัญชี

---

## 📦 Dependencies

- Odoo 14.0
- Python 3.7+
- requests library (สำหรับ test script)

```bash
pip install requests
```

---

## 📞 Support

หากมีปัญหาหรือข้อสงสัย:
1. อ่านเอกสารใน `API_SHIPMENT_DOCUMENTATION.md`
2. ลองใช้ `test_api.py` เพื่อทดสอบ
3. ตรวจสอบ `CHANGELOG.md` สำหรับรายละเอียดการเปลี่ยนแปลง
4. ดู Odoo log สำหรับ error messages

---

## 📜 License

Internal use only - NPD System

---

## ✨ Credits

**Developer:** System Team  
**Date:** October 2025  
**Version:** 1.0.0  
**Status:** ✅ Production Ready
