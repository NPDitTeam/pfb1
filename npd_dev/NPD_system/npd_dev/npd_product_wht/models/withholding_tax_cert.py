# -*- coding: utf-8 -*-
"""หนังสือรับรองหัก ณ ที่จ่าย — ล็อกเลขที่เอกสาร และกันเลขซ้ำ

เลขที่ออกจาก ir.sequence รหัส "withholding.tax" อัตโนมัติอยู่แล้ว
(โมดูล withholding_tax_cert_amount ออกให้ตอนใบเปลี่ยนเป็น done)
แต่ฟิลด์เดิมเปิด states ให้แก้ได้ตอนร่าง และวิวของโมดูลนั้นเอาช่องมาแสดง
พนักงานจึงพิมพ์เลขเองได้ ทำให้เลขชนกับที่ sequence จะออกให้ทีหลัง
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    # ตัด states ออก เพื่อไม่ให้พิมพ์เลขเองแม้อยู่ในสถานะร่าง
    # (ยังแสดงให้เห็นเหมือนเดิม แค่แก้ไม่ได้)
    name = fields.Char(
        string="Number",
        compute="_compute_wt_cert_data",
        store=True,
        readonly=True,
        states={},
        tracking=True,
    )

    @api.constrains("name", "company_id")
    def _check_wt_cert_name_unique(self):
        """เลขหนังสือรับรองห้ามซ้ำกันภายในบริษัทเดียวกัน

        ไม่นับใบที่ยกเลิก เพราะเลขของใบที่ยกเลิกถือว่าคืนเข้าระบบแล้ว
        และไม่นับใบที่ยังไม่มีเลข (ร่างที่ยังไม่ถึงขั้นออกเลข)

        เช็กตอนเลขถูกตั้ง/ถูกแก้เท่านั้น ไม่ผูกกับ state เพราะใบเก่าที่เลข
        ซ้ำกันอยู่ก่อนแล้วจะถูกบล็อกตอนเปลี่ยนสถานะ ทั้งที่ไม่ได้แตะเลข
        """
        for rec in self:
            name = (rec.name or "").strip()
            if not name or rec.state == "cancel":
                continue
            domain = [
                ("id", "!=", rec.id),
                ("name", "=", name),
                ("state", "!=", "cancel"),
            ]
            if "company_id" in self._fields:
                domain.append(("company_id", "=", rec.company_id.id))
            duplicate = self.sudo().search(domain, limit=1)
            if duplicate:
                raise ValidationError(
                    _(
                        'เลขที่หนังสือรับรองหัก ณ ที่จ่าย "%s" ถูกใช้ไปแล้ว\n\n'
                        "ซ้ำกับเอกสาร id=%s (สถานะ %s)\n"
                        "เลขที่ชุดนี้ระบบออกให้อัตโนมัติ ถ้าเลขชนกันแปลว่า "
                        "ลำดับเลขของบริษัทนี้ถูกตั้งค่าซ้ำ กรุณาแจ้งฝ่ายบัญชี"
                    )
                    % (name, duplicate.id, duplicate.state)
                )
