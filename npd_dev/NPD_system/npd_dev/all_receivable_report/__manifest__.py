{
    'name': 'All Receivable Report - ลูกหนี้ทั้งหมด',
    'version': '14.0.1.0.2',
    'summary': 'รายงานลูกหนี้ทั้งหมดและลูกหนี้ค้าง Tax',
    'description': '''
        รายงานลูกหนี้ทั้งหมด
        - ดึงข้อมูลจาก account.move (ใบแจ้งหนี้)
        - แสดงเฉพาะที่ค้างชำระ
        - กรองตามวันที่และสาขา
        - แสดงข้อมูล: ชื่อลูกค้า, เบอร์, ที่อยู่, สาขา, ค่าเช่า, ค่าปรับหาย, ค่าปรับชำรุด, VAT 7%
        - Group by ลูกค้า
        
        รายงานลูกหนี้ค้าง Tax
        - ดึงข้อมูลหัก ณ ที่จ่าย จาก account.payment
        - แสดงข้อมูลลูกค้าและยอดหัก ณ ที่จ่าย
    ''',
    'author': 'NPD Development',
    'category': 'Accounting/Reports',
    'depends': ['base', 'account', 'branch', 'stock_report_dashboard'],
    'data': [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/all_receivable_wizard_view.xml',
        'views/all_receivable_view.xml',
        'views/tax_receivable_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
