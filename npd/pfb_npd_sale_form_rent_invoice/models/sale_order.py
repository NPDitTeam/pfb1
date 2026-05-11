import datetime
import logging

_logger = logging.getLogger(__name__)

from odoo import api, fields, models
from bahttext import bahttext  # ให้แน่ใจว่าโมดูล bahttext ติดตั้งอยู่

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    confirmed_time = fields.Datetime(string='Confirmed Time')
    fielddatetime = fields.Datetime(
        string="Date Time",
        default=lambda self: fields.Datetime.now(),
    )

    # def action_confirm(self):
    #     _logger.info("Time-TesT: %s", self.fielddatetime or "No datetime set")
    #     return super(SaleOrder, self).action_confirm()


    def get_date_baht_text(self):
        return bahttext(self.commitment_date) if self.commitment_date else "ไม่มีวันที่กำหนด"

    def get_rent_daily(self):
        total_rent = sum(line.price_unit * line.product_uom_qty for line in self.order_line)
        return total_rent

    def get_total_baht_text(self):
        total_amount = self.pfb_amount + self.amount_total
        if not total_amount:
            return "0 บาท"
        text = bahttext(total_amount)
        satang = round((total_amount - int(total_amount)) * 100)
        if satang == 1:
            text = text.replace('เอ็ดสตางค์', 'หนึ่งสตางค์')
        return text

    def action_confirm(self):
        # เรียกฟังก์ชันของคลาสพ่อ
        res = super(SaleOrder, self).action_confirm()
        # _logger.info("Time : ", self.confirmed_time)
        # เก็บเวลาที่กดปุ่มยืนยันสำหรับแต่ละเรคอร์ด
        for order in self:
            order.confirmed_time = datetime.datetime.now()

        return res

    def some_function(self):
        order = self.env['sale.order']  # ใช้ ID ของคำสั่งซื้อที่ถูกต้อง
        return {
            'order': order,
        }





