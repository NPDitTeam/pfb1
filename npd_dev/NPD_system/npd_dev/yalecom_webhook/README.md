# Yalecom Webhook Integration

โมดูลสำหรับรับข้อมูล Callback จาก Yalecom API

## 📋 คุณสมบัติ

- ✅ รับข้อมูลสายโทรเข้า/ออก (Call Callback)
- ✅ เก็บประวัติการโทร
- ✅ เชื่อมโยงกับลูกค้า/คู่ค้าอัตโนมัติ
- ✅ บันทึก Webhook Log สำหรับ Debug
- ✅ รองรับไฟล์เสียง (Recording URL)

## 🔧 การติดตั้ง

1. ติดตั้งโมดูลผ่าน Apps
2. ค้นหา "Yalecom Webhook Integration"
3. คลิก Install

## 🌐 Webhook URL

```
https://your-odoo-domain.com/api/yalecom/callback
```

**ส่ง URL นี้ให้ทาง Yalecom เพื่อตั้งค่า Callback**

## 📡 Endpoint ที่รองรับ

| Method | URL | รายละเอียด |
|--------|-----|-----------|
| POST | `/api/yalecom/callback` | รับ Callback (JSON) |
| POST | `/api/yalecom/callback` | รับ Callback (HTTP Form) |
| GET | `/api/yalecom/callback` | ทดสอบ Endpoint |

## 📄 ตัวอย่างข้อมูลที่รับได้

```json
{
    "event": "call_end",
    "call_id": "abc123",
    "type": "inbound",
    "caller": "0891234567",
    "called": "021234567",
    "status": "answered",
    "duration": 120,
    "start_time": "2025-01-19 10:00:00",
    "end_time": "2025-01-19 10:02:00",
    "recording_url": "https://..."
}
```

## 🔑 Event Types ที่รองรับ

| Event | รายละเอียด |
|-------|-----------|
| `call_start`, `call_ringing`, `ringing` | สายเรียกเข้า |
| `call_answer`, `answered` | รับสาย |
| `call_end`, `ended`, `hangup` | วางสาย |
| `call_missed`, `missed`, `no_answer` | ไม่รับสาย |

## ⚙️ การตั้งค่า

1. ไปที่เมนู **Yalecom → การตั้งค่า → ตั้งค่า Yalecom**
2. คัดลอก Webhook URL
3. ส่งให้ Yalecom ตั้งค่า

## 📝 หมายเหตุ

- โครงสร้างข้อมูลขึ้นอยู่กับ API Document ของ Yalecom
- หากโครงสร้างข้อมูลไม่ตรง สามารถปรับแก้ได้ที่ `controllers/main.py`
- ดู Webhook Log เพื่อตรวจสอบข้อมูลที่ได้รับจริง

## 🔗 API Document

https://client.yalecom.co.th/api/document#api-callback

## 👨‍💻 ผู้พัฒนา

NPD Development
