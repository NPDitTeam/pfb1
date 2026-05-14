# -*- coding: utf-8 -*-
{
    'name': 'ควบคุมการแก้ไขค่าประกันที่ต้องการ',
    'version': '14.0.1.0.0',
    'category': 'การขาย',
    'summary': 'ควบคุมสิทธิ์การแก้ไขฟิลด์ "กรอกจำนวนค่าประกันที่ต้องการ" ในใบสั่งขายตามการตั้งค่าผู้ใช้',
    'description': 'โมดูลนี้ช่วยให้คุณสามารถจำกัดหรืออนุญาตการแก้ไขฟิลด์ค่าประกันที่ต้องการ (pfb_required_insurance_premium) ในหน้า Sale Order ตามสิทธิ์ของแต่ละ User',
    'author': 'NPD System',
    'website': 'https://github.com/npd-system',
    'depends': ['base', 'sale', 'pfb_npd_all_customs'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
