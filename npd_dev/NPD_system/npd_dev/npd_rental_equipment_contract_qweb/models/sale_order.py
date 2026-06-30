# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, models, fields

# ----------------------------------------------------------------------------
# เลขที่สัญญาเช่าเต็ม = {ตัวย่อบริษัท}{เลขรัน}.{ลำดับ}/{ทั้งหมด}
#   เช่น  nb-26061900004.3/3
#   - ตัวย่อบริษัท (nb-)  : default ตาม DB ที่ login + แก้เองได้ผ่านปุ่ม
#   - เลขรัน (26061900004): จาก ir.sequence (copy=True ซ้ำเอกสารใช้เลขเดิม)
#   - .X/Y               : X=ลำดับเอกสารใน deposit_ref, Y=จำนวนทั้งหมด
# ----------------------------------------------------------------------------

# Mapping DB -> ตัวย่อบริษัท (prefix เลขที่สัญญาเช่า) -- เป็น "ค่าเริ่มต้น"
DB_CONTRACT_PREFIX = {
    "NPD_S_Group_New_V2": "sg-",
    "NPD_S_Group_New": "sg-",
    "NPD_Intertrading_New": "in-",
    "NPD_Steeltech_New": "st-",
    "NPD_Bangkok_New": "nb-",
    "NPD_Logistics_New": "lg-",
}

# Mapping DB -> ชื่อบริษัท (ผู้ให้เช่า)
DB_COMPANY_NAME = {
    "NPD_S_Group_New_V2": u"บริษัท นภดล เอส กรุ๊ป จำกัด",
    "NPD_S_Group_New": u"บริษัท นภดล เอส กรุ๊ป จำกัด",
    "NPD_Intertrading_New": u"บริษัท นภดล อินเตอร์เทรดดิ้ง จำกัด",
    "NPD_Steeltech_New": u"บริษัท เอ็นพีดี สตีลเทค จำกัด",
    "NPD_Bangkok_New": u"บริษัท นภดล กรุงเทพ จำกัด",
    "NPD_Logistics_New": u"บริษัท เอ็นพีดี โลจิสติกส์ จำกัด",
}

# ชื่อเดือนไทยแบบเต็ม (index = เลขเดือน 1-12)
THAI_MONTHS = (
    "",
    u"มกราคม", u"กุมภาพันธ์", u"มีนาคม", u"เมษายน", u"พฤษภาคม", u"มิถุนายน",
    u"กรกฎาคม", u"สิงหาคม", u"กันยายน", u"ตุลาคม", u"พฤศจิกายน", u"ธันวาคม",
)

# ชื่อเดือนไทยแบบย่อ (index = เลขเดือน 1-12)
THAI_MONTHS_ABBR = (
    "",
    u"ม.ค.", u"ก.พ.", u"มี.ค.", u"เม.ย.", u"พ.ค.", u"มิ.ย.",
    u"ก.ค.", u"ส.ค.", u"ก.ย.", u"ต.ค.", u"พ.ย.", u"ธ.ค.",
)

# ---- แปลงจำนวนเงินเป็นข้อความไทย (บาท/สตางค์) ----
_BT_NUM = (u"", u"หนึ่ง", u"สอง", u"สาม", u"สี่", u"ห้า", u"หก", u"เจ็ด", u"แปด", u"เก้า")
_BT_UNIT = (u"", u"สิบ", u"ร้อย", u"พัน", u"หมื่น", u"แสน")


def _bt_read(n):
    """อ่านจำนวนเต็มเป็นข้อความไทย (ยังไม่รวมหน่วยบาท)"""
    if n == 0:
        return u""
    if n >= 1000000:
        return _bt_read(n // 1000000) + u"ล้าน" + _bt_read(n % 1000000)
    s = str(n)
    length = len(s)
    res = u""
    for i, ch in enumerate(s):
        d = int(ch)
        if d == 0:
            continue
        pos = length - i - 1  # 0=หน่วย, 1=สิบ, ...
        if pos == 0:
            res += u"เอ็ด" if (d == 1 and length > 1) else _BT_NUM[d]
        elif pos == 1:
            res += u"สิบ" if d == 1 else (u"ยี่สิบ" if d == 2 else _BT_NUM[d] + u"สิบ")
        else:
            res += _BT_NUM[d] + _BT_UNIT[pos]
    return res


def bahttext(amount):
    """1,250.50 -> หนึ่งพันสองร้อยห้าสิบบาทห้าสิบสตางค์"""
    amount = round(float(amount or 0.0), 2)
    baht = int(amount)
    satang = int(round((amount - baht) * 100))
    if baht == 0 and satang == 0:
        return u"ศูนย์บาทถ้วน"
    text = u""
    if baht > 0:
        text += _bt_read(baht) + u"บาท"
    if satang > 0:
        text += _bt_read(satang) + u"สตางค์"
    elif baht > 0:
        text += u"ถ้วน"
    return text


class SaleOrder(models.Model):
    _inherit = "sale.order"

    rental_contract_no = fields.Char(
        string=u"เลขรันสัญญาเช่า",
        copy=True,  # ซ้ำเอกสารใช้เลขเดิม ไม่รันเลขใหม่
        readonly=True,
        help=u"เลขรันจาก ir.sequence (ส่วน 26061900004) -- ไม่รวมตัวย่อบริษัท",
    )
    rental_contract_prefix = fields.Char(
        string=u"ตัวย่อบริษัท",
        copy=True,
        default=lambda self: DB_CONTRACT_PREFIX.get(self._cr.dbname, ""),
        help=u"ตัวย่อบริษัทหน้าเลขที่สัญญา (เช่น nb-) ค่าเริ่มต้นตาม DB เปลี่ยนได้ผ่านปุ่ม",
    )
    rental_contract_full = fields.Char(
        string=u"เลขที่สัญญาเช่า",
        compute="_compute_rental_contract_full",
        help=u"เลขที่สัญญาเช่าเต็ม = ตัวย่อ + เลขรัน + .ลำดับ/ทั้งหมด",
    )

    @api.depends("rental_contract_prefix", "rental_contract_no")
    def _compute_rental_contract_full(self):
        for order in self:
            num = order.rental_contract_no or ""
            if not num:
                order.rental_contract_full = ""
                continue
            prefix = order.rental_contract_prefix or DB_CONTRACT_PREFIX.get(
                order._cr.dbname, ""
            )
            order.rental_contract_full = "%s%s%s" % (
                prefix,
                num,
                order._get_rental_deposit_position(),
            )

    def _get_rental_deposit_position(self):
        """ส่วนต่อท้าย /N  โดย N = จำนวนชุดใน deposit_ref + 1 (นับเอกสารนี้เพิ่มเสมอ)
          - deposit_ref ว่าง   (0 ชุด) -> /1
          - deposit_ref 1 ชุด          -> /2
          - deposit_ref 2 ชุด          -> /3
          - deposit_ref 3 ชุด          -> /4"""
        self.ensure_one()
        return "/%d" % self._get_rental_doc_count()  # แสดง /N เสมอ (รวม /1)

    def _get_rental_doc_count(self):
        """จำนวนเอกสารในกลุ่ม N = จำนวน SO ใน deposit_ref + 1 (นับเอกสารนี้)"""
        self.ensure_one()
        refs = []
        if "deposit_ref" in self._fields:
            refs = [r.strip() for r in (self.deposit_ref or "").split(",") if r.strip()]
        return len(refs) + 1

    def _get_rental_contract_base(self):
        """เลขที่สัญญา = ตัวย่อ + เลขรัน (ไม่รวม /N) -- ใช้ในรายงานสัญญาเช่าเท่านั้น
        ส่วนฟอร์ม/รายงานอื่นใช้ rental_contract_full (มี /N)"""
        self.ensure_one()
        num = self.rental_contract_no or ""
        if not num:
            return ""
        prefix = self.rental_contract_prefix or DB_CONTRACT_PREFIX.get(
            self._cr.dbname, ""
        )
        return "%s%s" % (prefix, num)

    def action_open_contract_prefix_wizard(self):
        """ปุ่ม header: เปิด wizard เปลี่ยนตัวย่อบริษัทของเลขที่สัญญาเช่า"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": u"เปลี่ยนตัวย่อบริษัท",
            "res_model": "npd.rental.contract.prefix.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_prefix": self.rental_contract_prefix
                or DB_CONTRACT_PREFIX.get(self._cr.dbname, ""),
            },
        }

    def _get_rental_lessor_name(self):
        """ชื่อบริษัทผู้ให้เช่าตามฐานข้อมูลที่ login (fallback = ชื่อบริษัทในระบบ)"""
        return DB_COMPANY_NAME.get(self._cr.dbname) or (
            self.company_id.name if self.company_id else ""
        )

    def _format_thai_date(self, value):
        """แปลง date/datetime -> {'day','month(ไทยเต็ม)','year(พ.ศ.)'}
        ถ้าเป็น datetime จะแปลง timezone ผู้ใช้ก่อน (เก็บเป็น UTC)"""
        if not value:
            return {"day": "", "month": "", "year": ""}
        if isinstance(value, datetime):
            value = fields.Datetime.context_timestamp(self, value)
        return {
            "day": str(value.day),
            "month": THAI_MONTHS[value.month],
            "year": str(value.year + 543),
        }

    def _get_rental_contract_date_thai(self):
        """วันที่ทำสัญญา (date_order) รูปแบบไทย"""
        self.ensure_one()
        return self._format_thai_date(self.date_order)

    def _get_rental_return_date_thai(self):
        """วันกำหนดส่งคืน (end_rent_date) รูปแบบไทย"""
        self.ensure_one()
        value = self.end_rent_date if "end_rent_date" in self._fields else False
        return self._format_thai_date(value)

    def _get_rental_start_date_thai(self):
        """วันที่เริ่มต้นการเช่า (start_rent_date) รูปแบบไทย"""
        self.ensure_one()
        value = self.start_rent_date if "start_rent_date" in self._fields else False
        return self._format_thai_date(value)

    def _get_rental_start_short_thai(self):
        """วันที่เริ่มต้นการเช่า (start_rent_date) แบบย่อไทย เช่น 22 มิ.ย.69"""
        self.ensure_one()
        value = self.start_rent_date if "start_rent_date" in self._fields else False
        return self._get_rental_short_thai_date(value)

    def _get_rental_amount_total(self):
        """ยอดรวม (amount_total) จัดรูปแบบ #,##0.00"""
        self.ensure_one()
        return "{:,.2f}".format(self.amount_total or 0.0)

    def _get_rental_invoice_amount(self):
        """ยอดที่ 'ชำระแล้วจริง' จากใบแจ้งหนี้ที่ลงบันทึกแล้ว (posted)
        - ชำระเต็ม  -> ยอดเต็มใบ
        - ชำระบางส่วน -> ยอดที่ชำระจริง (ยอดเต็ม - ยอดค้าง)
        - ยังไม่ชำระเลย -> 0 (ไม่แสดง)"""
        self.ensure_one()
        if "invoice_ids" not in self._fields:
            return 0.0
        invs = self.invoice_ids.filtered(
            lambda m: m.state == "posted"
            and m.move_type == "out_invoice"
            and m.payment_state in ("paid", "in_payment", "partial")
        )
        return sum((inv.amount_total - inv.amount_residual) for inv in invs)

    def _get_rental_invoice_amount_display(self):
        """ยอดเงินใบแจ้งหนี้ #,##0.00 (ว่างถ้าไม่มี)"""
        self.ensure_one()
        amt = self._get_rental_invoice_amount()
        return "{:,.2f}".format(amt) if amt else ""

    def _get_rental_invoice_amount_text(self):
        """ยอดเงินใบแจ้งหนี้เป็นตัวอักษรไทย (ว่างถ้าไม่มี)"""
        self.ensure_one()
        amt = self._get_rental_invoice_amount()
        return bahttext(amt) if amt else ""

    def _get_rental_short_thai_date(self, value=None):
        """วันที่แบบย่อไทย เช่น '19 มิ.ย.69' (default = date_order)"""
        self.ensure_one()
        dt = value if value is not None else self.date_order
        if not dt:
            return ""
        if isinstance(dt, datetime):
            dt = fields.Datetime.context_timestamp(self, dt)
        return "%d %s%02d" % (dt.day, THAI_MONTHS_ABBR[dt.month], (dt.year + 543) % 100)

    def _get_rental_duration(self):
        """ระยะเวลาเช่า (วันที่ต้องเช่า = pfb_date_of_rent) -- guard เผื่อฟิลด์ไม่มี"""
        self.ensure_one()
        if "pfb_date_of_rent" in self._fields and self.pfb_date_of_rent:
            return str(self.pfb_date_of_rent)
        return ""

    def _get_rental_lessor_address(self):
        """ที่อยู่ผู้ให้เช่า ดึงจาก branch_id.address (เหมือนใบกำกับการเช่า)
        fallback = ที่อยู่บริษัท -- คืนเป็นบรรทัดเดียว"""
        self.ensure_one()
        addr = ""
        if "branch_id" in self._fields and self.branch_id and hasattr(
            self.branch_id, "address"
        ):
            addr = self.branch_id.address or ""
        if not addr and self.company_id:
            c = self.company_id
            parts = [
                c.street, c.street2, c.city,
                c.state_id.name if c.state_id else "",
                c.zip,
            ]
            addr = " ".join(p for p in parts if p)
        return " ".join((addr or "").split())  # ยุบขึ้นบรรทัด/ช่องว่างซ้ำเป็นช่องเดียว

    def _get_rental_on_site(self):
        """หน้างาน (on_site) -- guard เผื่อฟิลด์ไม่มี"""
        self.ensure_one()
        if "on_site" in self._fields:
            return self.on_site or ""
        return ""

    def _get_rental_branch_name(self):
        """ชื่อสาขา (branch_id) -- guard เผื่อฟิลด์ไม่มี"""
        self.ensure_one()
        if "branch_id" in self._fields and self.branch_id:
            return self.branch_id.name or ""
        return ""

    def _get_rental_customer_info(self):
        """ข้อมูลผู้เช่า (ลูกค้า) สำหรับหัวสัญญา -> {'name','vat','address','phone'}"""
        self.ensure_one()
        p = self.partner_id
        if not p:
            return {"name": "", "vat": "", "address": "", "phone": ""}
        addr_parts = [
            p.street,
            p.street2,
            p.city,
            p.state_id.name if p.state_id else "",
            p.zip,
            p.country_id.name if p.country_id else "",
        ]
        address = " ".join([x for x in addr_parts if x])
        return {
            "name": p.name or "",
            "vat": p.vat or "",
            "address": address,
            "phone": p.phone or p.mobile or "",
        }

    def _ensure_rental_contract_no(self):
        """สร้างเลขที่สัญญาเช่าให้ครั้งแรก แล้วเก็บไว้ (ไม่เปลี่ยนถ้ามีแล้ว)"""
        seq_obj = self.env["ir.sequence"]
        for order in self:
            if not order.rental_contract_no:
                # ใช้ค่าจาก ir.sequence ตรง ๆ (prefix sg/in/st/nb/lg กำหนดในเลขรันเอง)
                order.rental_contract_no = seq_obj.next_by_code("npd.rental.contract") or ""
        return True

    def _is_rental_contract_order(self, order):
        """เป็นใบขายประเภท 'เช่า' (rent) หรือไม่ -- กันกรณีโมดูล pfb_so_type ไม่ได้ติดตั้ง"""
        if "pfb_so_type" in order._fields:
            return order.pfb_so_type == "rent"
        return False

    def action_open_rent_invoice(self):
        """Compatibility shim.

        วิวฟอร์มขาย (เก็บใน DB / Studio) มีปุ่มที่เรียก method นี้ แต่โค้ดต้นทางหายไป
        ทำให้ตอน validate วิว (เมื่อมีโมดูลใด inherit ฟอร์มขาย) ล้มด้วย
        'action_open_rent_invoice is not a valid action on sale.order'
        จึงใส่ stub ไว้ให้ปุ่มยัง valid -> ถ้ามีใบแจ้งหนี้ก็เปิดดูตามมาตรฐาน
        ** ทางที่ถูกต้องคือไปลบ/แก้ปุ่มที่ค้างใน Studio view ของ sale.order **
        """
        if hasattr(super(SaleOrder, self), "action_open_rent_invoice"):
            return super(SaleOrder, self).action_open_rent_invoice()
        if hasattr(self, "action_view_invoice"):
            return self.action_view_invoice()
        return False

    def action_confirm(self):
        """เมื่อกดยืนยัน (state -> 'sale' / ใบสั่งขาย) ถ้าประเภท = rent ให้สร้างเลขที่สัญญาเช่าทันที"""
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if self._is_rental_contract_order(order) and not order.rental_contract_no:
                order._ensure_rental_contract_no()
        return res
