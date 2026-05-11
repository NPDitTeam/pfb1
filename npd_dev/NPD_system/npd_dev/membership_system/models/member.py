from odoo import models, fields, api
import requests
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class MembershipMember(models.Model):
    _name = 'membership.member'
    _description = 'Membership Member'

    member_id = fields.Char(string="Member ID", unique=True)
    name = fields.Char(string="Name")
    phone = fields.Char(string="Phone")
    member_type = fields.Char(string="Member Type")
    birth_date = fields.Date(string="Birth Date")
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], string="Gender")
    points = fields.Integer(string="Points")
    used_points = fields.Integer(string="Used Points")
    signup_date = fields.Date(string="Signup Date")
    # end_date = fields.Date(compute='_fund_balance')
    #
    # @api.onchange("end_date")
    # def _fund_balance(self):
    #     for record1 in self:
    #         record1.end_date = '2023-03-09'
    #         self.action_fetch_member_data()
            # print('**********************************************************************')

    # @api.model
    # def default_get(self, fields):
    #     _logger.info('default_get called: Fetching member data')
    #     res = super(MembershipMember, self).default_get(fields)
    #     self.action_fetch_member_data()
    #     return res

    def action_fetch_member_data(self):
        _logger.info('Fetching member data from API')
        self._fetch_member_data()

    def _fetch_member_data(self):
        url = "https://api-beloyalty-productions.betaskthai.com/Member/NPD"
        payload = {"token": "Uc850d4b60c5b51d3034e44ecf52e4687"}
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('status'):
                for member in data.get('data', []):
                    try:
                        # แปลงวันที่จาก API โดยใช้เฉพาะวัน เดือน ปี
                        signup_date_str = member.get('วันที่สมัคร')
                        signup_date = datetime.strptime(signup_date_str, '%a, %d %b %Y %H:%M:%S %Z').date()
                    except ValueError:
                        signup_date = None

                    # ตรวจสอบความครบถ้วนของข้อมูล
                    if not all([member.get('memberId'), member.get('ชื่อลูกค้า'), member.get('เบอร์โทรศัพท์'), member.get('ระดับสมาชิก'), member.get('วันเกิด'), member.get('เพศ')]):
                        _logger.warning('Incomplete data for member: %s', member)
                        continue

                    # อัพเดตหรือสร้างสมาชิกใหม่
                    self._update_or_create_member(member, signup_date)
            else:
                _logger.error('API Error: %s', data.get('message'))
        else:
            _logger.error('API Request failed with status code %s', response.status_code)

        # ลบสมาชิกที่ไม่มีค่า member_id หลังจากการสร้างหรืออัพเดตเสร็จสิ้น
        self._delete_incomplete_members()

    def _update_or_create_member(self, member, signup_date):
        existing_member = self.search([('member_id', '=', member.get('memberId'))])
        if existing_member:
            existing_member.write({
                'name': member.get('ชื่อลูกค้า'),
                'phone': member.get('เบอร์โทรศัพท์'),
                'member_type': member.get('ระดับสมาชิก'),
                'birth_date': member.get('วันเกิด'),
                'gender': 'female' if member.get('เพศ') == 'female' else 'male',
                'points': member.get('คะแนนปัจจุบัน'),
                'used_points': member.get('คะแนนที่สะสม'),
                'signup_date': signup_date,
            })
            _logger.info('Member updated: %s', member.get('memberId'))
        else:
            self.create({
                'member_id': member.get('memberId'),
                'name': member.get('ชื่อลูกค้า'),
                'phone': member.get('เบอร์โทรศัพท์'),
                'member_type': member.get('ระดับสมาชิก'),
                'birth_date': member.get('วันเกิด'),
                'gender': 'female' if member.get('เพศ') == 'female' else 'male',
                'points': member.get('คะแนนปัจจุบัน'),
                'used_points': member.get('คะแนนที่สะสม'),
                'signup_date': signup_date,
            })
            _logger.info('New member created: %s', member.get('memberId'))

    def _delete_incomplete_members(self):
        incomplete_members = self.search([('member_id', '=', False)])
        incomplete_members.unlink()
        _logger.info('Deleted incomplete members: %s', incomplete_members)
