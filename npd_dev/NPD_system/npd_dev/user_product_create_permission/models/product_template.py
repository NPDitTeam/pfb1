# -*- coding: utf-8 -*-
##############################################################################
#
#    ไฟล์: product_template.py
#    วัตถุประสงค์: เพิ่มเงื่อนไขตรวจสอบสิทธิ์การสร้างสินค้า
#
#    คำอธิบาย:
#    ---------
#    โมเดลนี้ทำการ inherit (สืบทอด) จากโมเดล product.template
#    และเพิ่มการตรวจสอบสิทธิ์ก่อนการสร้างสินค้าใหม่
#    
#    การทำงาน:
#    ---------
#    1. Override method create() ของ product.template
#    2. ตรวจสอบว่าผู้ใช้มีสิทธิ์ can_create_product หรือไม่
#    3. ถ้าไม่มีสิทธิ์ จะแสดง error และไม่อนุญาตให้สร้าง
#    4. ถ้ามีสิทธิ์ จะดำเนินการสร้างตามปกติ
#
#    หมายเหตุ:
#    ---------
#    - เงื่อนไขนี้จะตรวจสอบเฉพาะตอนสร้างสินค้าใหม่เท่านั้น
#    - ไม่กระทบกับการแก้ไขสินค้าที่มีอยู่แล้ว
#    - ไม่กระทบกับส่วนงานอื่นๆ ของระบบ
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    """
    สืบทอดโมเดล product.template เพื่อเพิ่มเงื่อนไขตรวจสอบสิทธิ์การสร้างสินค้า
    
    โมเดล product.template คือโมเดลหลักที่เก็บข้อมูลสินค้าในระบบ Odoo
    การใช้ _inherit จะทำให้เราสามารถ override method โดยไม่ต้องแก้ไขโค้ดต้นฉบับ
    """
    
    # ระบุว่าจะสืบทอดจากโมเดลใด
    _inherit = 'product.template'
    
    @api.model
    def create(self, vals):
        """
        Override method create เพื่อตรวจสอบสิทธิ์ก่อนสร้างสินค้า
        
        Parameters:
        -----------
        vals : dict
            ค่าของฟิลด์ที่จะสร้าง
            
        Returns:
        --------
        recordset
            record ของสินค้าที่สร้างใหม่
            
        Raises:
        -------
        UserError
            ถ้าผู้ใช้ไม่มีสิทธิ์สร้างสินค้า (can_create_product = False)
        """
        
        # ดึงข้อมูลผู้ใช้ปัจจุบัน
        current_user = self.env.user
        
        # ตรวจสอบว่าผู้ใช้มีสิทธิ์สร้างสินค้าหรือไม่
        # ถ้า can_create_product = False จะแสดง error
        if not current_user.can_create_product:
            raise UserError(_(
                'คุณไม่มีสิทธิ์สร้างสินค้า!\n\n'
                'กรุณาติดต่อผฝ่าย IT '
            ))
        
        # ถ้ามีสิทธิ์ ให้ดำเนินการสร้างสินค้าตามปกติ
        # เรียก method create() ของ parent class
        return super(ProductTemplate, self).create(vals)
