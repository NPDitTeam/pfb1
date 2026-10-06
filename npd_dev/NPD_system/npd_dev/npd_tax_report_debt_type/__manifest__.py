{
    'name': 'NPD Thai Tax Report - Debt Type Columns',
    'version': '14.0.1.0.0',
    'summary': 'รายงานภาษี (Thai Tax Reports): เพิ่มคอลัมน์ประเภทหนี้ และประเภทหนี้ (บ้านเขียว)',
    'description': """
ฝ่ายบัญชีขอให้รายงานภาษีบอกว่ารายการนี้เป็นหนี้ประเภทไหน

* ประเภทหนี้ = ช่อง "ประเภทสินค้า" (reason_code_id) ของใบแจ้งหนี้
* ประเภทหนี้ (บ้านเขียว) = bk_debt_type ของใบแจ้งหนี้ (มีเฉพาะฐานที่ติดตั้ง
  baankheaw_debt_payment ฐานอื่นคอลัมน์นี้ว่าง)

เอกสารภาษีที่เกิดจากรายการรับชำระ (ภาษีขายรอรับชำระ) อ่านค่าจากใบแจ้งหนี้
ที่รายการนั้นตัดชำระ ไม่ใช่จากรายการรับชำระเอง เพราะช่องประเภทสินค้าของ
รายการรับชำระถูกเติมค่าเริ่มต้นไว้ทุกใบ ไม่ได้บอกประเภทหนี้จริง
    """,
    'category': 'Accounting',
    'author': 'NPD',
    'depends': ['l10n_th_tax_report', 'npd_print_select_account'],
    'data': ['reports/tax_report_templates.xml'],
    'installable': True,
    'auto_install': False,
}
