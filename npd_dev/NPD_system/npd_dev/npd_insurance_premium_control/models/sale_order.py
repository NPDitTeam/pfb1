# -*- coding: utf-8 -*-
import json
import logging
from lxml import etree

from odoo import api, models, SUPERUSER_ID

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )

        if view_type != 'form':
            return res

        try:
            doc = etree.XML(res['arch'])
            modified = False

            # 1. ลบ insurance group ที่ซ้ำซ้อน (เก็บเฉพาะอันแรก)
            tables = doc.xpath("//table[.//field[@name='pfb_amount_insurance']]")
            if len(tables) > 1:
                for t in tables[1:]:
                    wrapper = t.getparent()
                    depth = 0
                    while wrapper is not None and wrapper.tag != 'group' and depth < 5:
                        wrapper = wrapper.getparent()
                        depth += 1
                    if wrapper is not None and wrapper.tag == 'group':
                        parent = wrapper.getparent()
                        if parent is not None:
                            parent.remove(wrapper)
                            modified = True

            # 1b. ลบ stat button "รับเงินประกัน" (action_view_rent) ที่ซ้ำซ้อน
            rent_buttons = doc.xpath("//button[@name='action_view_rent']")
            if len(rent_buttons) > 1:
                for b in rent_buttons[1:]:
                    parent = b.getparent()
                    if parent is not None:
                        parent.remove(b)
                        modified = True

            # 2. ตรวจสอบสิทธิ์ user
            user = self.env.user
            allowed = (
                user.id == SUPERUSER_ID
                or getattr(user, 'allow_edit_insurance_premium', False)
            )

            nodes = doc.xpath("//field[@name='pfb_required_insurance_premium']")
            for node in nodes:
                # อ่าน modifiers ที่ Odoo computed มาแล้ว
                mods_str = node.get('modifiers')
                mods = json.loads(mods_str) if mods_str else {}

                if allowed:
                    # มีสิทธิ์ → ลบ readonly ออกจากทั้ง attribute และ modifiers
                    if 'readonly' in node.attrib:
                        del node.attrib['readonly']
                    if 'attrs' in node.attrib:
                        # parse attrs และลบ readonly ในนั้น
                        try:
                            attrs = eval(node.get('attrs'))
                            if isinstance(attrs, dict) and 'readonly' in attrs:
                                del attrs['readonly']
                                if attrs:
                                    node.set('attrs', str(attrs))
                                else:
                                    del node.attrib['attrs']
                        except Exception:
                            pass
                    if 'readonly' in mods:
                        del mods['readonly']
                    node.set('modifiers', json.dumps(mods))
                    modified = True
                else:
                    # ไม่มีสิทธิ์ → บังคับ readonly ทั้ง attribute และ modifiers
                    node.set('readonly', '1')
                    mods['readonly'] = True
                    node.set('modifiers', json.dumps(mods))
                    modified = True

            if modified:
                res['arch'] = etree.tostring(doc, encoding='unicode')
        except Exception as e:
            _logger.warning(
                "npd_insurance_premium_control: failed to process sale.order form view: %s", e
            )

        return res
