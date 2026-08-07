# Copyright 2021 Pierre Verkest <pierreverkest84@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.tools import html2plaintext


class SaleOrder(models.Model):

    _inherit = "sale.order"

    terms_template_id = fields.Many2one(
        "sale.terms_template",
        string="Terms and conditions template",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    # note = fields.Html(readonly=True, states={"draft": [("readonly", False)]})
    # เปลี่ยนจาก Html เป็น Text เพื่อให้ช่อง "หมายเหตุ" เป็นกล่องกรอกข้อความธรรมดา
    # (ไม่มีแถบเครื่องมือจัดรูปแบบ) และส่งต่อเป็นข้อความล้วนไปยัง narration ของใบแจ้งหนี้
    note = fields.Text(readonly=False, string="หมายเหตุ")

    @api.onchange("terms_template_id")
    def _onchange_terms_template_id(self):
        if self.terms_template_id:
            # แม่แบบเงื่อนไข (text) เป็น Html จึงแปลงเป็นข้อความล้วนก่อนใส่ในหมายเหตุ
            value = self.terms_template_id.get_value(self)
            self.note = html2plaintext(value) if value else value
