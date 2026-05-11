from odoo import models, fields, api
import requests
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class Promotion(models.Model):
    _name = 'promotion.promotion'
    _description = 'Promotion'

    promotion_id = fields.Char(string="Promotion ID", unique=True)
    promotion_name = fields.Char(string="Promotion Name")
    promotion_sub_name = fields.Char(string="Promotion Sub Name")
    promotion_picture = fields.Char(string="Promotion Picture URL")
    promotion_details = fields.Text(string="Promotion Details")
    promotion_expiry_date = fields.Date(string="Promotion Expiry Date")  # เปลี่ยนเป็น Date field
    limit_expiry = fields.Char(string="Limit Expiry")
    shop_id = fields.Char(string="Shop ID")
    # end_date = fields.Date(compute='_fund_balance')
    #
    # @api.onchange("end_date")
    # def _fund_balance(self):
    #     for record1 in self:
    #         record1.end_date = '2023-03-09'
    #         self.action_fetch_promotion_data()

    record_status = fields.Selection([
        ('Y', 'Active'),
        ('N', 'Inactive')
    ], string="Record Status", default='Y')

    def action_fetch_promotion_data(self):
        _logger.info('Fetching promotion data from API')
        self._fetch_promotion_data()

    def _fetch_promotion_data(self):
        url = "https://api-beloyalty-productions.betaskthai.com/promotion/NPD"
        payload = {"token": "Uc850d4b60c5b51d3034e44ecf52e4687"}
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('status'):
                for promo in data.get('data', []):
                    try:
                        # แปลงวันที่จาก API โดยใช้เฉพาะวัน เดือน ปี
                        promotion_expiry_date_str = promo.get('promotionExpiryDate')
                        promotion_expiry_date = datetime.strptime(promotion_expiry_date_str, '%a, %d %b %Y %H:%M:%S %Z').date()

                        # อัพเดตหรือสร้างรายการ Promotion ใหม่
                        self._update_or_create_promotion(promo, promotion_expiry_date)
                    except ValueError:
                        _logger.error('Invalid date format for promotion: %s', promo)
            else:
                _logger.error('API Error: %s', data.get('message'))
        else:
            _logger.error('API Request failed with status code %s', response.status_code)

        # ลบรายการที่ไม่มีค่า promotion_id หลังจากการสร้างหรืออัพเดตเสร็จสิ้น
        self._delete_incomplete_promotions()

    def _update_or_create_promotion(self, promo, promotion_expiry_date):
        existing_promotion = self.search([('promotion_id', '=', promo.get('id'))])
        vals = {
            'promotion_name': promo.get('promotionName', ''),
            'promotion_sub_name': promo.get('promotionSubName', ''),
            'promotion_picture': promo.get('promotionPicture', ''),
            'promotion_details': promo.get('promotionDetails', ''),
            'promotion_expiry_date': promotion_expiry_date,  # ใช้วันที่ที่แปลงแล้ว
            'limit_expiry': promo.get('limitExpri', ''),
            'shop_id': promo.get('shopId', ''),
            'record_status': promo.get('RECORD_STATUS', 'Y'),
        }

        if existing_promotion:
            existing_promotion.write(vals)
            _logger.info('Promotion updated: %s', promo.get('id'))
        else:
            vals['promotion_id'] = promo.get('id')
            self.create(vals)
            _logger.info('New promotion created: %s', promo.get('id'))

    def _delete_incomplete_promotions(self):
        # ลบรายการที่ไม่มีค่า promotion_id
        incomplete_promotions = self.search([('promotion_id', '=', False)])
        incomplete_promotions.unlink()
        _logger.info('Deleted incomplete promotions: %s', incomplete_promotions)
