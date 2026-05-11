# Security - คำอธิบายไฟล์ ir.model.access.csv

## รูปแบบ CSV
```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

## อธิบายแต่ละคอลัมน์

| คอลัมน์ | ความหมาย | ตัวอย่าง |
|---------|----------|----------|
| `id` | ID เฉพาะของสิทธิ์ (ต้องไม่ซ้ำ) | `access_npd_commission_report` |
| `name` | ชื่อสิทธิ์ (แสดงใน UI) | `npd.commission.report` |
| `model_id:id` | Model ที่กำหนดสิทธิ์ | `model_npd_commission_report` |
| `group_id:id` | กลุ่มผู้ใช้ที่ได้สิทธิ์ | `account.group_account_user` |
| `perm_read` | สิทธิ์อ่าน (1=ได้, 0=ไม่ได้) | `1` |
| `perm_write` | สิทธิ์แก้ไข | `1` |
| `perm_create` | สิทธิ์สร้าง | `1` |
| `perm_unlink` | สิทธิ์ลบ | `1` |

## วิธีแปลงชื่อ Model เป็น model_id:id

เปลี่ยน `.` เป็น `_` และเติม `model_` ข้างหน้า:
- `npd.commission.report` → `model_npd_commission_report`
- `npd.commission.report.line` → `model_npd_commission_report_line`

## กลุ่มผู้ใช้ที่ใช้บ่อย

| group_id:id | ความหมาย |
|-------------|----------|
| `base.group_user` | ผู้ใช้ทั่วไป |
| `account.group_account_user` | พนักงานบัญชี |
| `account.group_account_manager` | ผู้จัดการบัญชี |
| `base.group_system` | Admin |

## หมายเหตุ
- ไฟล์ CSV ไม่รองรับคอมเมนต์ `#`
- ห้ามมี space หลัง comma
- บรรทัดแรกต้องเป็น header เสมอ
