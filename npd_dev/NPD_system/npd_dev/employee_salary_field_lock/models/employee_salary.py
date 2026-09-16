# -*- coding: utf-8 -*-
import json
from lxml import etree

from odoo import models, fields, api
from odoo.exceptions import UserError


class EmployeeSalary(models.Model):
    _inherit = 'employee.salary'

    # ฟิลด์ที่ยัง "แก้ไขได้" แม้ผู้ใช้จะถูกล็อค (ตามที่ผู้ใช้กำหนด: สาขา + ตำแหน่ง)
    SALARY_LOCK_EDITABLE_FIELDS = ('branch_id', 'position_id')

    # แท็บที่ยังแก้ไขได้ทั้งแท็บแม้ผู้ใช้จะถูกล็อค
    # ข้อมูลเอกสารแรงงานต่างชาติเป็นงานธุรการที่ต้องอัปเดตบ่อย (วันหมดอายุบัตร/
    # Passport/Work Permit) และไม่เกี่ยวกับค่าจ้าง จึงไม่ควรโดนล็อคไปด้วย
    # อ้างด้วยชื่อแท็บ ฟิลด์ที่เพิ่มในแท็บนี้ภายหลังจึงแก้ไขได้เองโดยไม่ต้องมาไล่เพิ่มชื่อ
    SALARY_LOCK_EDITABLE_PAGES = ('foreign_worker',)

    # ฟิลด์ค่าจ้าง/เงินเพิ่มที่ "ซ่อน" ไปเลยเมื่อผู้ใช้ถูกล็อค (ไม่ใช่แค่แก้ไม่ได้)
    HIDDEN_SALARY_FIELDS = (
        'salary',
        'cost_of_living',
        'position_allowance',
        'experience_allowance',
        'professional_allowance',
    )

    # ฟิลด์การเงินที่บังคับใช้การล็อคระดับ ORM ด้วย (กันช่องทางอื่นนอกจากฟอร์ม)
    # จำกัดเฉพาะฟิลด์การเงิน เพื่อไม่ให้กระทบปุ่ม/กระบวนการที่เขียนฟิลด์อื่น
    # (เช่น ปุ่มรีเซ็ตอุปกรณ์, ปุ่ม sync ที่เขียน device_id / sync_status)
    LOCKED_SALARY_FIELDS = [
        # หน้า "ข้อมูลบริษัท" / "รายได้อื่นๆ"
        'salary',
        'cost_of_living',
        'position_allowance',
        'experience_allowance',
        'professional_allowance',
        # หน้า "ข้อมูลเงินเดือนและภาษี"
        'enable_social_security',
        'social_security_condition',
        'social_security_fixed_amount',
        'social_security_start_date',
        'enable_tax',
        'tax_condition',
        'tax_exception',
        'tax_start_date_condition',
    ]

    def _salary_lock_active(self):
        """True เมื่อผู้ใช้ปัจจุบันถูกตั้งค่าให้ล็อคการแก้ไข (และไม่ใช่ superuser)"""
        return bool(self.env.user.lock_salary_fields) and not self.env.su

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(EmployeeSalary, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)

        # ล็อคทั้งฟอร์มให้แก้ไขไม่ได้ ยกเว้นสาขา (branch_id) ตำแหน่ง (position_id)
        # และแท็บข้อมูลต่างชาติ ส่วนค่าจ้าง/เงินเพิ่มซ่อนไปเลย
        if view_type == 'form' and self._salary_lock_active():
            doc = etree.XML(res['arch'])

            # ฟิลด์ในแท็บที่ยกเว้น — เทียบด้วยตัวโหนด ไม่ใช่ชื่อ เพราะฟิลด์ชื่อเดียวกัน
            # อาจมีอยู่ในแท็บอื่นด้วย (เช่น passport_number) และแท็บอื่นยังต้องถูกล็อค
            editable_nodes = set()
            for page_name in self.SALARY_LOCK_EDITABLE_PAGES:
                for node in doc.xpath("//page[@name='%s']//field" % page_name):
                    editable_nodes.add(node)

            for node in doc.xpath("//field"):
                name = node.get('name')
                modifiers = json.loads(node.get('modifiers') or '{}')

                if name in self.HIDDEN_SALARY_FIELDS:
                    modifiers['invisible'] = True
                    modifiers['readonly'] = True
                    # ฟิลด์ที่ซ่อนต้องไม่บังคับกรอก ไม่งั้นตอนบันทึกจะติด
                    # "ฟิลด์ไม่ถูกต้อง" โดยที่ผู้ใช้มองไม่เห็นช่องให้แก้ (salary required)
                    modifiers['required'] = False
                    node.set('modifiers', json.dumps(modifiers))
                    continue

                if name in self.SALARY_LOCK_EDITABLE_FIELDS or node in editable_nodes:
                    continue

                # อัปเดต modifiers ให้เป็น readonly แบบไม่มีเงื่อนไข
                modifiers['readonly'] = True
                node.set('modifiers', json.dumps(modifiers))

            # แท็บที่เหลือแต่ฟิลด์ที่ซ่อนทั้งหมด (เช่น "รายได้อื่นๆ") ไม่ต้องโชว์แท็บเปล่า
            for page in doc.xpath("//page"):
                page_fields = page.xpath(".//field")
                if page_fields and all(
                        f.get('name') in self.HIDDEN_SALARY_FIELDS for f in page_fields):
                    page_modifiers = json.loads(page.get('modifiers') or '{}')
                    page_modifiers['invisible'] = True
                    page.set('modifiers', json.dumps(page_modifiers))

            res['arch'] = etree.tostring(doc, encoding='unicode')

        return res

    def write(self, vals):
        # ป้องกันการแก้ไขฟิลด์การเงินในระดับ ORM (กันช่องทางอื่นนอกจากฟอร์ม) —
        # จะบล็อกเฉพาะเมื่อค่าจริงมีการเปลี่ยนแปลงเท่านั้น เพื่อไม่ให้กระทบการบันทึกซ้ำค่าเดิม
        if self._salary_lock_active():
            blocked = [f for f in self.LOCKED_SALARY_FIELDS if f in vals]
            if blocked:
                for rec in self:
                    for field_name in blocked:
                        field = rec._fields[field_name]
                        # แปลงทั้งค่าเดิมและค่าใหม่ให้อยู่ในรูปแบบเดียวกัน เพื่อเทียบได้ทุกชนิดฟิลด์
                        # (Float / Boolean / Selection / Date)
                        try:
                            new_value = field.convert_to_cache(vals[field_name], rec)
                            old_value = field.convert_to_cache(rec[field_name], rec)
                        except Exception:
                            new_value = vals[field_name]
                            old_value = rec[field_name]
                        if new_value != old_value:
                            raise UserError(
                                'คุณไม่มีสิทธิ์แก้ไขข้อมูลค่าจ้าง/เงินเพิ่ม/ประกันสังคม/ภาษี '
                                'ของพนักงาน (บัญชีผู้ใช้ของคุณถูกตั้งค่าให้ล็อคการแก้ไข)'
                            )
        return super(EmployeeSalary, self).write(vals)
