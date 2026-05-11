# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

WHT_CERT_INCOME_TYPE = [
    ("1", "1. เงินเดือน ค่าจ้าง ฯลฯ 40(1)"),
    ("2", "2. ค่าธรรมเนียม ค่านายหน้า ฯลฯ 40(2)"),
    ("3", "3. ค่าแห่งลิขสิทธิ์ ฯลฯ 40(3)"),
    ("4A", "4. ดอกเบี้ย ฯลฯ 40(4)ก"),
    (
        "4B11",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (1.1) "
        "กิจการที่ต้องเสียภาษีเงินได้นิติบุคคลร้อยละ 30 ของกำไรสุทธิ",
    ),
    (
        "4B12",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (1.2) "
        "กิจการที่ต้องเสียภาษีเงินได้นิติบุคคลร้อยละ 25 ของกำไรสุทธิ",
    ),
    (
        "4B13",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (1.3) "
        "กิจการที่ต้องเสียภาษีเงินได้นิติบุคคลร้อยละ 20 ของกำไรสุทธิ",
    ),
    (
        "4B14",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (1.4) "
        "กิจการที่ต้องเสียภาษีเงินได้นิติบุคคลร้อยละ อื่นๆ (ระบุ) ของกำไรสุทธิ",
    ),
    (
        "4B21",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (2.1) "
        "กำไรสุทธิกิจการที่ได้รับยกเว้นภาษีเงินได้นิติบุคคล",
    ),
    (
        "4B22",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (2.2) "
        "ได้รับยกเว้นไม่ต้องนำมารวมคำนวณเป็นรายได้",
    ),
    (
        "4B23",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (2.3) "
        "กำไรสุทธิส่วนที่หักผลขาดทุนสุทธิยกมาไม่เกิน 5 ปี",
    ),
    (
        "4B24",
        "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (2.4) "
        "กำไรที่รับรู้ทางบัญชีโดยวิธีส่วนได้เสีย",
    ),
    ("4B25", "4. เงินปันผล เงินส่วนแบ่งกำไร ฯลฯ 40(4)ข (2.5) อื่นๆ (ระบุ)"),
    ("5", "5. ค่าจ้างทำของ ค่าบริการ ค่าเช่า ค่าขนส่ง ฯลฯ 3 เตรส"),
    ("6", "6. อื่นๆ (ระบุ)"),
]

class WithholdingTaxType(models.Model):
    _name = 'withholding.tax.type'
    _description = 'WithholdingTaxType'
    _rec_name = 'wt_cert_income_type'
    

    wt_cert_income_type = fields.Selection(
        selection=WHT_CERT_INCOME_TYPE, string="Type of Income", required=True
    )
    percent_tax = fields.Float('Percent Tax')
    title_number_form = fields.Char('Title number form')

    _sql_constraints = [
        ('wt_cert_income_type', 'unique(wt_cert_income_type)', 'Type of Income must be unique !'),
    ]

class WithholdingTaxCertLine(models.Model):
    _inherit = "withholding.tax.cert.line"

    @api.onchange("wt_cert_income_type")
    def _onchange_wt_cert_income_type(self):
        super()._onchange_wt_cert_income_type()
        wht_type = self.env['withholding.tax.type'].search([('wt_cert_income_type','=',self.wt_cert_income_type)],limit=1)
        self.wt_percent = wht_type and wht_type.percent_tax or 0