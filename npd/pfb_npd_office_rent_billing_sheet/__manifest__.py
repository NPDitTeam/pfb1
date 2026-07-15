{
    'name': 'ใบแจ้งหนี้ค่าเช่าพื้นที่สำนักงาน',
    'version': '14.0.1.0.0',
    'summary': 'Office space rental invoice form on account.move',
    'description': """
สร้างแบบฟอร์มใบแจ้งหนี้ "ใบแจ้งหนี้ค่าเช่าพื้นที่สำนักงาน" ตามรูปแบบใบแจ้งหนี้/ใบวางบิล
(pfb_npd_account_billing_sheets) แต่พิมพ์จากหน้า account.move
โดยปุ่มพิมพ์จะอยู่ในเมนู "พิมพ์" ของหน้าใบแจ้งหนี้
และช่อง "รายการ" ในแบบฟอร์มจะดึงรายการจากใบแจ้งหนี้ (invoice_line_ids) ที่กำลังพิมพ์
""",
    'author': 'Devtest',
    'depends': ['base', 'sale', 'account'],
    'data': [
        'report/pfb_npd_office_rent_billing_sheet.xml',
    ],
    'installable': True,
}
