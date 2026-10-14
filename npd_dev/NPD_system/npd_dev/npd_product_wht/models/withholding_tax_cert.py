# -*- coding: utf-8 -*-
"""หนังสือรับรองหัก ณ ที่จ่าย — ล็อกเลขที่เอกสาร และกันเลขซ้ำ

เลขที่ออกจาก ir.sequence รหัส "withholding.tax" อัตโนมัติอยู่แล้ว
(โมดูล withholding_tax_cert_amount ออกให้ตอนใบเปลี่ยนเป็น done)
แต่ฟิลด์เดิมเปิด states ให้แก้ได้ตอนร่าง และวิวของโมดูลนั้นเอาช่องมาแสดง
พนักงานจึงพิมพ์เลขเองได้ ทำให้เลขชนกับที่ sequence จะออกให้ทีหลัง

เลขที่มีวันที่ฝังอยู่ (WT-MMDDYY-NNNN) ออกตามฟิลด์ Date ตอนออกเลข
ถ้าแก้ Date ทีหลัง เลขจะไม่ตรงกับวันที่ จึงห้ามแก้ Date ของใบที่มีเลขแล้ว
ต้องยกเลิกใบเดิมแล้วสร้างใหม่ให้ได้เลขของวันที่ใหม่
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    @api.model
    def _npd_next_wt_number(self, date, company):
        """ขอเลขถัดไปตามวันที่ของใบ (ไม่ใช่วันที่กดทำรายการ)

        sequence "withholding.tax" ไม่ได้ผูกบริษัท (company_id ว่าง)
        โค้ดเดิมค้นด้วย company_id = บริษัท จึงหาไม่เจอแล้วตกไป next_by_code
        แบบไม่ส่งวันที่ เลขเลยออกตามวันนี้ next_by_code หาได้ทั้งของบริษัทและของกลาง
        """
        return self.env["ir.sequence"].with_company(company).next_by_code(
            "withholding.tax", sequence_date=date
        )

    @api.depends("payment_id", "move_id", "state")
    def _compute_wt_cert_data(self):
        # ออกเลขก่อน withholding_tax_cert_amount ซึ่งจะได้เลขของวันนี้
        # (ใบจาก payment ระบบเดิมตั้งชื่อตาม payment เองใน context wt_account_ids)
        if not self._context.get("wt_account_ids"):
            for rec in self:
                if not rec.name and rec.state == "done":
                    rec.name = self._npd_next_wt_number(
                        rec.date, rec.company_id or self.env.company
                    )
        return super()._compute_wt_cert_data()

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

    def write(self, vals):
        if "date" in vals:
            new_date = fields.Date.to_date(vals["date"])
            self.filtered(
                lambda c: c.date != new_date
            )._check_wt_cert_date_locked()
        return super().write(vals)

    def _check_wt_cert_date_locked(self):
        """ห้ามเปลี่ยนวันที่ของใบที่ออกเลขแล้ว (ไม่นับใบที่ยกเลิก)

        เรียกกับใบที่วันที่กำลังจะเปลี่ยน ทั้งจากหน้าใบ WT เอง
        และจากปุ่ม "สร้าง WHT อัตโนมัติ" ของ Advance Clear / Voucher
        """
        locked = self.filtered(lambda c: c.name and c.state != "cancel")
        if not locked:
            return
        msgs = [_("ใบหัก ณ ที่จ่ายต่อไปนี้ออกเลขตามวันที่ไปแล้ว เปลี่ยนวันที่ไม่ได้:")]
        for cert in locked:
            msgs.append(
                "  • %s (วันที่ %s, %s)"
                % (
                    cert.name,
                    cert.date and cert.date.strftime("%d/%m/%Y") or "-",
                    cert.supplier_partner_id.display_name or "-",
                )
            )
        msgs.append("")
        msgs.append(
            _(
                "ถ้าวันที่ผิด ให้เปิดใบ WT นั้น กด Set to Draft แล้วกด Cancel "
                "จากนั้นสร้างใบใหม่ (ถ้ามาจาก Advance Clear / Voucher "
                "ให้กดปุ่ม \"สร้าง WHT อัตโนมัติ\" อีกครั้ง) "
                "ระบบจะออกเลขใหม่ตามวันที่ที่ถูกต้อง"
            )
        )
        raise UserError("\n".join(msgs))
