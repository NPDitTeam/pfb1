{
    'name': 'ใบแจ้งหนี้/ใบวางบิล(เฉพาะค่าประกัน)',
    'version': '14.0.1.0.0',
    'summary': 'Order Rent - Billing Note (deposit only) with bank bill-payment QR/Barcode/Comp Code',
    'description': "ใบแจ้งหนี้/ใบวางบิล เฉพาะค่าประกัน — แสดงเฉพาะค่าประกันสุทธิ, "
                   "ไม่คิดภาษีหัก ณ ที่จ่าย 5% (ชำระเต็มจำนวนเสมอ), "
                   "QR/บาร์โค้ด/Comp Code อ้างอิงใบแจ้งหนี้ค่าประกัน (INS)",
    'author': 'Devtest',
    # อาศัยโมดูลใบวางบิลค่าเช่าสำหรับของที่ใช้ร่วมกัน (res.company.bill_payment_biller_id + view ของมัน)
    # เพื่อไม่ให้ฟิลด์ซ้ำซ้อนบนฟอร์มบริษัท
    'depends': ['base', 'sale', 'pfb_npd_sale_form_Billing_sheet_rent'],
    'data': [
        "report/pfb_npd_sale_form_Billing_sheet_deposit.xml",
    ],
}
