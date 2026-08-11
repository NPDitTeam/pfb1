{
    'name': 'NPD Rent Invoice - Overdue',
    'version': '14.0.1.0.0',
    'summary': 'ใบกำกับการเช่าหนี้ค้างชำระ',
    'description': """
ใบกำกับการเช่าหนี้ค้างชำระ
==========================
คัดลอกจาก pfb_npd_sale_form_rent_invoice โดยเพิ่ม:

1. ดึงรายการสินค้าจาก SO อื่นของลูกค้ารายเดียวกัน ที่เข้าเงื่อนไขทั้ง 2 ข้อ
   - มีใบแจ้งหนี้ หรือ ใบแจ้งหนี้ค่าประกัน ที่ค้างชำระ/ค้างชำระบางส่วน
   - ยังคืนสินค้าไม่ครบ (ดูจากการจัดส่ง)
   โดยไม่นับ SO ใบที่กำลังพิมพ์อยู่
2. เพิ่มคอลัมน์ "อ้างอิงเลขเอกสาร" ในตารางสินค้า
   รายการที่ดึงมาไม่ถูกนำไปคิดยอดรวมของใบกำกับ (ยอดรวมคิดเฉพาะรายการของตัวเอง)
3. เพิ่มตาราง "สรุปยอดค้างชำระ" ต่อจากตารางสินค้า
   (เลข SO / เลขใบแจ้งหนี้ / ประเภท / ยอดค้างชำระ)
""",
    'author': 'Devtest',
    'category': 'Sales',
    'depends': ['base', 'sale', 'account', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'report/npd_rent_invoice_overdue.xml',
        'views/sale_order_overdue.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
