{
    'name': 'ใบแจ้งหนี้/ใบวางบิล - ติดตามหนี้',
    'version': '14.0.2.3.0',
    'summary': 'รายงานใบแจ้งหนี้/ใบวางบิล สำหรับติดตามหนี้ (ค่าเช่า/ค่าปรับชำรุด/ค่าปรับหาย/ค่า Tax)',
    'description': "",
    'author': 'NPD',
    'depends': ['base', 'npd_debt_tracking'],
    'data': [
        "report/pfb_npd_sale_form_Billing_sheet.xml",
        "report/pfb_npd_sale_form_Billing_sheet_damage.xml",
        "report/pfb_npd_sale_form_Billing_sheet_lost.xml",
        "report/pfb_npd_sale_form_Billing_sheet_tax.xml",
        "views/debt_tracking_inherit_views.xml",
    ],
}