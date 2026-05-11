from odoo import models, fields, api
import requests
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ActivityReport(models.Model):
    _name = 'activity.report'
    _description = 'Activity Report'

    activity_id = fields.Char(string="Activity ID")
    line_user_id = fields.Char(string="Line User ID")
    member_id = fields.Char(string="Member ID")
    join_date = fields.Date(string="Join Date")
    field1_value = fields.Char(string="Field 1 Value")
    field2_value = fields.Char(string="Field 2 Value")
    field3_value = fields.Char(string="Field 3 Value")
    field4_value = fields.Char(string="Field 4 Value")
    shop_id = fields.Char(string="Shop ID")
    record_status = fields.Selection([
        ('Y', 'Active'),
        ('N', 'Inactive')
    ], string="Record Status", default='Y')

    def action_fetch_activity_data(self):
        _logger.info('Fetching activity data from API')
        self._fetch_activity_data()

    def _fetch_activity_data(self):
        url = "https://api-beloyalty-productions.betaskthai.com/ActivityData/NPD"
        payload = {"token": "Uc850d4b60c5b51d3034e44ecf52e4687"}
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('status'):
                for activity in data.get('data', []):
                    try:
                        join_date_str = activity.get('joinDate')
                        join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()

                        # Update or create a new Activity record
                        self._update_or_create_activity(activity, join_date)
                    except ValueError:
                        _logger.error('Invalid date format for activity: %s', activity)
            else:
                _logger.error('API Error: %s', data.get('message'))
        else:
            _logger.error('API Request failed with status code %s', response.status_code)

        self._delete_incomplete_activities()

    def _update_or_create_activity(self, activity, join_date):
        # Check for existing activity with the same activity_id and member_id
        existing_activity = self.search([
            ('activity_id', '=', activity.get('activityId')),
            ('member_id', '=', activity.get('memberId'))
        ])
        vals = {
            'line_user_id': activity.get('lineUserId', ''),
            'member_id': activity.get('memberId', ''),
            'join_date': join_date,
            'field1_value': activity.get('field1Value', ''),
            'field2_value': activity.get('field2Value', ''),
            'field3_value': activity.get('field3Value', ''),
            'field4_value': activity.get('field4Value', ''),
            'shop_id': activity.get('shopId', ''),
            'record_status': activity.get('RECORD_STATUS', 'Y'),
        }

        if existing_activity:
            existing_activity.write(vals)
            _logger.info('Activity updated: %s', activity.get('activityId'))
        else:
            vals['activity_id'] = activity.get('activityId')
            self.create(vals)
            _logger.info('New activity created: %s', activity.get('activityId'))

    def _delete_incomplete_activities(self):
        incomplete_activities = self.search([('activity_id', '=', False)])
        incomplete_activities.unlink()
        _logger.info('Deleted incomplete activities: %s', incomplete_activities)
