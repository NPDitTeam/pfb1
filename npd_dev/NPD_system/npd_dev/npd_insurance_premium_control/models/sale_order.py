# -*- coding: utf-8 -*-
import ast
import json
import logging
from lxml import etree

from odoo import api, models, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _parse_attrs(attrs_str):
    """Parse attrs string ที่อาจเป็น Python-literal หรือ JSON-style ก็ได้"""
    if not attrs_str:
        return None
    try:
        return ast.literal_eval(attrs_str)
    except Exception:
        try:
            return json.loads(attrs_str)
        except Exception:
            return None


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends(
        'order_line.pfb_quantity',
        'order_line.pfb_insurance_price',
        'pfb_dis_amount_insurance',
        'pfb_required_insurance_premium',
    )
    def _compute_amount_insurance(self):
        super()._compute_amount_insurance()
        for order in self:
            if order.pfb_required_insurance_premium:
                order.pfb_amount = order.pfb_required_insurance_premium
                order.pfb_amount_c = order.pfb_amount

    def write(self, vals):
        if (
            'pfb_required_insurance_premium' in vals
            and 'pfb_dis_amount_insurance' not in vals
        ):
            required = vals.get('pfb_required_insurance_premium') or 0.0
            if required and len(self) == 1:
                new_dis = (self.pfb_amount_insurance or 0.0) - required
                if new_dis < 0:
                    new_dis = 0.0
                vals = dict(vals, pfb_dis_amount_insurance=new_dis)
        return super().write(vals)

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

            # field ที่มี attrs readonly อิง deposit_ref ใน XML ต้นทาง
            target_fields = [
                'pfb_required_insurance_premium',
                'pfb_dis_amount_insurance',
            ]

            for fname in target_fields:
                nodes = doc.xpath("//field[@name=$name]", name=fname)
                for node in nodes:
                    mods_str = node.get('modifiers')
                    mods = json.loads(mods_str) if mods_str else {}

                    if allowed:
                        # มีสิทธิ์ → ลบ readonly ออกทุกระดับ
                        if 'readonly' in node.attrib:
                            del node.attrib['readonly']
                        if 'attrs' in node.attrib:
                            attrs = _parse_attrs(node.get('attrs'))
                            if isinstance(attrs, dict) and 'readonly' in attrs:
                                del attrs['readonly']
                                if attrs:
                                    node.set('attrs', str(attrs))
                                else:
                                    del node.attrib['attrs']
                        if 'readonly' in mods:
                            del mods['readonly']
                        node.set('modifiers', json.dumps(mods))
                        modified = True
                    elif fname == 'pfb_required_insurance_premium':
                        # ไม่มีสิทธิ์ → readonly เฉพาะตอน SO ยืนยันแล้ว (state in sale/done)
                        # ตอนเป็น QT/ใบเสนอราคา (draft/sent/cancel) ยังแก้ไขได้ปกติ
                        readonly_domain = [
                            '|',
                            ['deposit_ref', '!=', False],
                            ['state', 'in', ['sale', 'done']],
                        ]
                        if 'readonly' in node.attrib:
                            del node.attrib['readonly']
                        node.set('attrs', str({'readonly': readonly_domain}))
                        mods['readonly'] = readonly_domain
                        node.set('modifiers', json.dumps(mods))
                        modified = True

            if modified:
                res['arch'] = etree.tostring(doc, encoding='unicode')
        except Exception as e:
            _logger.warning(
                "npd_insurance_premium_control: failed to process sale.order form view: %s", e
            )

        return res
