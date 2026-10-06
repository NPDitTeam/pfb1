{
    'name': 'NPD Partner Tax Branch Check',
    'version': '14.0.1.0.0',
    'summary': 'บังคับกรอกรหัสสาขา (Tax Branch) ของลูกค้านิติบุคคล',
    'description': """
ฝ่ายบัญชีแจ้งว่าใบกำกับภาษีของลูกค้านิติบุคคลต้องมีรหัสสาขา (สำนักงานใหญ่ = 00000)
แต่ข้อมูลลูกค้าส่วนใหญ่ยังไม่ได้กรอก

* หน้าผู้ติดต่อ: Tax Branch เป็นช่องบังคับกรอกเมื่อเป็นบริษัท
* ใบสั่งขาย: เลือกลูกค้าที่เป็นบริษัทแต่ยังไม่มีรหัสสาขา ระบบเด้งหน้าต่างให้กรอก
  รหัสสาขา 5 หลักทันที แล้วบันทึกกลับไปที่ลูกค้า ถ้าปิดหน้าต่างโดยไม่กรอก
  ระบบจะล้างช่องลูกค้าในใบสั่งขายออก
    """,
    'category': 'Sales',
    'author': 'NPD',
    'depends': ['sale', 'l10n_th_partner'],
    'data': [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/res_partner_views.xml',
        'wizard/tax_branch_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
