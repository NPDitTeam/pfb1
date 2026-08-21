# -*- coding: utf-8 -*-
"""ทำให้ท้ายกระดาษของหนังสือทวงถามบ้านเขียวไม่ต้องพึ่งไฟล์ภายนอก

อาการ (21 ส.ค. 2026): หมายเหตุท้ายหนังสือไม่แสดงเลยสักหน้า

สาเหตุ
    wkhtmltopdf เรนเดอร์ header/footer เป็น "คนละเอกสาร" กับตัวเนื้อหา
    Odoo ประกอบเอกสาร footer ขึ้นจากเทมเพลต web.minimal_layout ซึ่งแนบ
    <link rel="stylesheet"> ชี้กลับมาที่ตัว Odoo เอง (/web/content/...)
    เวลาเรนเดอร์ wkhtmltopdf จึงต้องยิง HTTP กลับมาโหลดไฟล์เหล่านี้
    ถ้ารอบไหนโหลดไม่สำเร็จ (เซิร์ฟเวอร์ไม่ว่างรับ, ไม่มี session, URL เพี้ยน)
    มันจะทิ้งเอกสาร footer ทั้งก้อนเงียบ ๆ หมายเหตุเลยหายไปทั้งใบ
    ตรวจสอบแล้วเห็นข้อความ "Exit with code 1 due to network error"
    ในล็อกตอนสั่งพิมพ์

วิธีแก้
    ตัด <link>/<script src> ออกจากเอกสาร footer ของรายงานนี้
    หมายเหตุใช้ inline style ล้วนอยู่แล้ว จึงไม่ต้องใช้ CSS จากภายนอกเลย
    พอไม่มีอะไรต้องโหลด wkhtmltopdf ก็ไม่มีอะไรให้พลาด

    แก้เฉพาะรายงานตัวนี้ตัวเดียว รายงานอื่นทุกตัวยังทำงานเหมือนเดิม
"""
import re

from odoo import models

REPORT_NAME = 'baankheaw.report_baankheaw_collection_letter'

# <link ...> และ <script src="..."> ที่ต้องโหลดข้ามเครือข่าย
EXTERNAL_RES_RE = re.compile(
    rb'<link\b[^>]*>|<script\b[^>]*\bsrc=[^>]*>\s*</script>', re.I)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html):
        res = super()._prepare_html(html)
        # ต้นทางคืน {} ได้ถ้าหาเทมเพลต web.minimal_layout ไม่เจอ ปล่อยผ่านไปตามเดิม
        if not isinstance(res, tuple) or len(res) != 5:
            return res
        bodies, html_ids, header, footer, args = res
        if REPORT_NAME in self.mapped('report_name') and footer:
            is_text = isinstance(footer, str)
            raw = footer.encode('utf-8') if is_text else bytes(footer)
            raw = EXTERNAL_RES_RE.sub(b'', raw)
            footer = raw.decode('utf-8') if is_text else raw
        return bodies, html_ids, header, footer, args
