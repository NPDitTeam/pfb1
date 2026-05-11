from odoo import models, fields, api
import requests
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class PaymentConfirmation(models.Model):
    _name = 'payment.confirmation'
    _description = 'Payment Confirmation'

    payment_id = fields.Char(string="Payment ID", unique=True)
    package_id = fields.Char(string="Package ID")
    shop_id = fields.Char(string="Shop ID")
    amount = fields.Float(string="Amount")
    package_name = fields.Char(string="Package Name")
    status = fields.Selection([
        ('use', 'Used'),
        ('cancel', 'Cancelled')
    ], string="Status", default='use')
    chk_status = fields.Selection([
        ('ยืนยัน', 'Confirmed'),
        ('ยกเลิก', 'Cancelled')
    ], string="CHK Status")
    package_expire_date = fields.Date(string="Package Expiry Date")  # เปลี่ยนเป็น Date field
    payment_date = fields.Date(string="Payment Date")  # เปลี่ยนเป็น Date field
    remark = fields.Text(string="Remark")
    end_date = fields.Date(compute='_fund_balance')

    @api.onchange("end_date")
    def _fund_balance(self):
        for record1 in self:
            record1.end_date = '2023-03-09'
            self.action_fetch_payment_data()

    def action_fetch_payment_data(self):
        _logger.info('Fetching payment data from API')
        self._fetch_payment_data()

    def _fetch_payment_data(self):
        url = "https://api-beloyalty-productions.betaskthai.com/PackageLog/NPD"
        payload = {"token": "Uc850d4b60c5b51d3034e44ecf52e4687"}
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('status'):
                for payment in data.get('data', []):
                    try:
                        # แปลงวันที่จาก API โดยใช้เฉพาะวัน เดือน ปี
                        package_expire_date_str = payment.get('packageExpire')
                        package_expire_date = datetime.strptime(package_expire_date_str, '%Y-%m-%d %H:%M:%S').date()

                        payment_date_str = payment.get('CREATE_DATE')
                        payment_date = datetime.strptime(payment_date_str, '%a, %d %b %Y %H:%M:%S %Z').date()

                        # อัพเดตหรือสร้างรายการ Payment Confirmation ใหม่
                        self._update_or_create_payment(payment, package_expire_date, payment_date)
                    except ValueError:
                        _logger.error('Invalid date format for payment: %s', payment)
            else:
                _logger.error('API Error: %s', data.get('message'))
        else:
            _logger.error('API Request failed with status code %s', response.status_code)

        # ลบรายการที่ไม่มีค่า payment_id หลังจากการสร้างหรืออัพเดตเสร็จสิ้น
        self._delete_incomplete_payments()

    def _update_or_create_payment(self, payment, package_expire_date, payment_date):
        existing_payment = self.search([('payment_id', '=', payment.get('idPackageLog'))])
        vals = {
            'package_id': payment.get('packageId', ''),
            'shop_id': payment.get('shopId', ''),
            'amount': payment.get('amount', 0.0),
            'package_name': payment.get('packageName', ''),
            'status': payment.get('status', 'use'),
            'chk_status': payment.get('CHKstatus', ''),
            'package_expire_date': package_expire_date,  # เก็บเฉพาะวันที่
            'payment_date': payment_date,  # เก็บเฉพาะวันที่
            'remark': payment.get('remark', ''),
        }

        if existing_payment:
            existing_payment.write(vals)
            _logger.info('Payment updated: %s', payment.get('idPackageLog'))
        else:
            vals['payment_id'] = payment.get('idPackageLog')
            self.create(vals)
            _logger.info('New payment created: %s', payment.get('idPackageLog'))

    def _delete_incomplete_payments(self):
        # ลบรายการที่ไม่มีค่า payment_id
        incomplete_payments = self.search([('payment_id', '=', False)])
        incomplete_payments.unlink()
        _logger.info('Deleted incomplete payments: %s', incomplete_payments)
