from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)


class ScoreDashboard(models.Model):
    _name = 'score.dashboard'
    _description = 'Score Dashboard'

    token = fields.Char(string="Token", unique=True)
    service = fields.Char(string="Service")
    score = fields.Integer(string="Score")
    phone_number = fields.Char(string="Phone Number")
    price = fields.Float(string="Price")
    status = fields.Selection([
        ('used', 'Used'),
        ('unused', 'Unused')
    ], string="Status", default='used')
    branch = fields.Char(string="Branch")
    customer_name = fields.Char(string="Customer Name")
    end_date = fields.Date(compute='_fund_balance')

    @api.onchange("end_date")
    def _fund_balance(self):
        for record1 in self:
            record1.end_date = '2023-03-09'
            self.action_fetch_score_data()

    def action_fetch_score_data(self):
        _logger.info('Fetching score data from API')
        self._fetch_score_data()

    def _fetch_score_data(self):
        url = "https://api-beloyalty-productions.betaskthai.com/QRcode/NPD"
        payload = {"token": "Uc850d4b60c5b51d3034e44ecf52e4687"}
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('status'):
                for score_data in data.get('data', []):
                    token = score_data.get('token')
                    # ตรวจสอบว่า token ไม่ใช่ค่าว่าง ถ้าเป็นค่าว่างให้ลบรายการนั้น
                    if not token:
                        _logger.warning('Deleting score data with empty token: %s', score_data)
                        self._delete_score(score_data)
                        continue

                    try:
                        # อัพเดตหรือสร้างรายการ Score Dashboard ใหม่
                        self._update_or_create_score(score_data)
                    except ValueError:
                        _logger.error('Invalid data format for score data: %s', score_data)
                # ลบรายการที่มี token ว่างในฐานข้อมูล
                self._delete_incomplete_scores()
            else:
                _logger.error('API Error: %s', data.get('message'))
        else:
            _logger.error('API Request failed with status code %s', response.status_code)

    def _delete_score(self, score_data):
        """ลบข้อมูลที่ไม่มี token"""
        existing_score = self.search([('token', '=', score_data.get('token'))])
        if existing_score:
            existing_score.unlink()
            _logger.info('Deleted score data: %s', score_data.get('token'))

    def _delete_incomplete_scores(self):
        """ลบข้อมูลที่ไม่มี token จากฐานข้อมูล"""
        incomplete_scores = self.search([('token', '=', False)])
        if incomplete_scores:
            incomplete_scores.unlink()
            _logger.info('Deleted incomplete scores with empty tokens')

    def _delete_score(self, score_data):
        """ลบข้อมูลที่ไม่มี token"""
        existing_score = self.search([('token', '=', score_data.get('token'))])
        if existing_score:
            existing_score.unlink()
            _logger.info('Deleted score data: %s', score_data.get('token'))

    def _update_or_create_score(self, score_data):
        token = score_data.get('token')
        phone_number = score_data.get('เบอร์โทร')
        score = score_data.get('คะแนน')
        price = score_data.get('ราคา')

        # ตรวจสอบว่า token, phone_number, score, และ price ไม่เป็นค่าว่าง
        if not token or not phone_number or not score or not price:
            _logger.warning('Skipping score data with empty required fields: %s', score_data)
            return  # ข้ามข้อมูลนี้ไป ไม่ทำอะไรต่อ

        existing_score = self.search([('token', '=', token)])
        vals = {
            'service': score_data.get('บริการ', ''),
            'score': score,
            'phone_number': phone_number,
            'price': price,
            'status': score_data.get('status', 'used'),
            'branch': score_data.get('สาขา', ''),
            'customer_name': score_data.get('ชื่อลูกค้า', ''),
        }

        if existing_score:
            existing_score.write(vals)
            _logger.info('Score data updated: %s', token)
        else:
            vals['token'] = token
            self.create(vals)
            _logger.info('New score data created: %s', token)

    def _delete_incomplete_scores(self):
        # ลบรายการที่ไม่มีค่า token หรือฟิลด์ที่จำเป็น
        incomplete_scores = self.search([
            '|',
            ('token', '=', False),
            '|',
            ('phone_number', '=', False),
            '|',
            ('score', '=', False),
            ('price', '=', False),
        ])
        incomplete_scores.unlink()
        _logger.info('Deleted incomplete scores: %s', incomplete_scores)
