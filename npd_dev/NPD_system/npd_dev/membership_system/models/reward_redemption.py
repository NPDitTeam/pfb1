from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)

class RewardRedemption(models.Model):
    _name = 'reward.redemption'
    _description = 'Reward Redemption'

    reward_name = fields.Char(string="Reward Name")
    reward_points = fields.Integer(string="Reward Points")
    reward_method = fields.Char(string="Reward Method")
    description = fields.Text(string="Description")
    status = fields.Selection([
        ('open', 'Open'),
        ('claimed', 'Claimed')
    ], string="Status", default='open')
    member_id = fields.Char(string="Member ID")
    customer_name = fields.Char(string="Customer Name")
    remark = fields.Text(string="Remark")

    def action_fetch_reward_data(self):
        _logger.info('Fetching reward redemption data from API')
        self._fetch_reward_data()
        self._delete_incomplete_rewards()  # Delete rewards with empty reward_name after fetching data

    def _fetch_reward_data(self):
        url = "https://api-beloyalty-productions.betaskthai.com/RewardCode/NPD"
        payload = {"token": "Uc850d4b60c5b51d3034e44ecf52e4687"}
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            _logger.info("API Response Data: %s", data)  # Log the full API response

            rewards_data = data.get('data', [])
            _logger.info("Total rewards fetched: %d", len(rewards_data))  # Log the number of rewards fetched

            if data.get('status'):
                for reward in rewards_data:
                    reward_name = reward.get('ของรางวัล', '').strip()
                    if reward_name:  # Only process rewards with a non-empty name
                        _logger.info("Processing reward: %s", reward)  # Log individual reward data
                        self._update_or_create_reward(reward)
                    else:
                        _logger.warning('Reward name is empty, skipping reward: %s', reward)
            else:
                _logger.error('API Error: %s', data.get('message'))
        else:
            _logger.error('API Request failed with status code %s', response.status_code)

    def _update_or_create_reward(self, reward):
        reward_name = reward.get('ของรางวัล', '').strip()

        # ตรวจสอบและแปลงค่า status ให้ถูกต้อง
        status_map = {
            'open': 'open',
            'claimed': 'claimed'
        }
        status = status_map.get(reward.get('สถานะ', '').strip().lower(), 'open')

        # Check if required fields are present and valid
        if not reward_name or reward.get('คะแนนแลกของรางวัล', 0) <= 0:
            _logger.warning('Incomplete reward data, skipping reward: %s', reward)
            return

        existing_reward = self.search([
            ('reward_name', '=', reward_name),
            ('reward_points', '=', reward.get('คะแนนแลกของรางวัล', 0))
        ])

        vals = {
            'reward_name': reward_name,
            'reward_points': reward.get('คะแนนแลกของรางวัล', 0),
            'reward_method': reward.get('วิธีรับของรางวัล', ''),
            'description': reward.get('description', ''),
            'status': status,
            'member_id': reward.get('memberId', ''),
            'customer_name': reward.get('ชื่อลูกค้า', ''),
            'remark': reward.get('หมายเหตุ', ''),
        }

        if existing_reward:
            existing_reward.write(vals)
            _logger.info('Reward updated: %s', reward_name)
        else:
            self.create(vals)
            _logger.info('New reward created: %s', reward_name)

    def _delete_incomplete_rewards(self):
        incomplete_rewards = self.search([('reward_name', '=', False)])
        if incomplete_rewards:
            _logger.info('Incomplete rewards found, deleting: %s', incomplete_rewards)
            incomplete_rewards.unlink()
