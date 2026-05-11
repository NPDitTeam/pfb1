{
    'name': 'Stock Report Dashboard',
    'version': '1.0',
    'summary': 'รวมรายงานสต๊อกไว้ในโมดูลเดียว',
    'description': 'โมดูลนี้ช่วยรวมรายงานสต๊อกทั้งหมดของ Odoo ในหน้าเดียว',
    'author': 'Your Company',
    'depends': ['stock', 'base', 'account', 'sale','branch'],  # เพิ่ม base ถ้ายังไม่มี
    'data': [
        'security/ir.model.access.csv',
        'views/stock_dashboard_view.xml',  # ✅ โหลดไฟล์ menu หลัก ก่อน!
        # 'views/stock_dashboard_view_report.xml',
        'views/sale_order_rent_cash_report_view.xml',
        'views/monthly_penalty_report_view.xml',
        'views/monthly_penalty_report_view_may.xml',
        'views/sale_order_report_rent_view.xml',
        'views/sale_order_report_invoice_detail_view.xml',
        'views/monthly_penalty_report_wizard_view.xml',
        'views/monthly_penalty_report_wizard_view_may.xml',
        'views/stock_report_wizard_view.xml',
        'views/stock_report_view.xml',
        'views/sale_order_report_invoice_wizard_view.xml',
        'views/sale_order_report_invoice_detail_branch_view.xml',
        'views/partner_ageing_form.xml',
    ],
    'images': ['static/description/icon.png'],  # ✅ ต้องเพิ่มบรรทัดนี้
    'installable': True,
    'application': True,
    'auto_install': False,
}
