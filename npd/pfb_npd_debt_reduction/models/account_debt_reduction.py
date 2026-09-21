from odoo import models, fields, api, _
from bahttext import bahttext

class AccountPayment(models.Model):
    _inherit = 'account.move'

    debt_reduction_note = fields.Text(
        string='หมายเหตุ',
        copy=False,
        help='หมายเหตุที่จะแสดงในช่อง "เหตุผลในการลดหนี้" บนแบบฟอร์มใบลดหนี้',
    )

    def get_baht_text_debt_reduction(self):
        # discount_taken = self.wht_amt_net - self.amount_tax
        discount_taken = self.amount_untaxed

        return bahttext(discount_taken)

    def get_reference_payments_debt_reduction(self):
        """ใบรับชำระ (CUST.IN) ที่ใบกำกับภาษีต้นทางของใบลดหนี้อ้างอิงอยู่"""
        self.ensure_one()
        if not self.reversed_entry_id:
            return self.env['account.payment']
        return self.reversed_entry_id._get_reconciled_payments().filtered(lambda p: p.state == 'posted')

    def get_thai_date_short_debt_reduction(self, date_value):
        """แปลงวันที่เป็นรูปแบบไทยย่อ เช่น 10 ก.ค. 69"""
        if not date_value:
            return ''
        months = {1: 'ม.ค.', 2: 'ก.พ.', 3: 'มี.ค.', 4: 'เม.ย.', 5: 'พ.ค.', 6: 'มิ.ย.',
                  7: 'ก.ค.', 8: 'ส.ค.', 9: 'ก.ย.', 10: 'ต.ค.', 11: 'พ.ย.', 12: 'ธ.ค.'}
        return '%s %s %s' % (date_value.strftime('%d'), months[date_value.month],
                             str(date_value.year + 543)[-2:])

    def get_reference_date_text_debt_reduction(self):
        """ลงวันที่ของใบรับชำระที่อ้างอิง ถ้าไม่พบให้ใช้วันที่ของใบลดหนี้เอง"""
        self.ensure_one()
        dates = []
        for payment_date in self.get_reference_payments_debt_reduction().mapped('date'):
            if payment_date and payment_date not in dates:
                dates.append(payment_date)
        if not dates and self.invoice_date:
            dates = [self.invoice_date]
        return ', '.join(self.get_thai_date_short_debt_reduction(d) for d in dates)
