{
    'name': 'ใบแจ้งหนี้/ใบวางบิล(เฉพาะค่าเช่า)',
    'version': '14.0.1.0.0',
    'summary': 'Order Rent - Billing Note (rental only) with bank bill-payment QR/Barcode/Comp Code',
    'description': "ใบแจ้งหนี้/ใบวางบิล เฉพาะค่าเช่า — ตัดค่าประกันออก, สร้าง QR/บาร์โค้ด/Comp Code ตามรูปแบบธนาคาร",
    'author': 'Devtest',
    'depends': ['base', 'sale'],
    'data': [
        "views/res_company_views.xml",
        "views/sale_order_views.xml",
        "report/pfb_npd_sale_form_Billing_sheet_rent.xml",
    ],
}
