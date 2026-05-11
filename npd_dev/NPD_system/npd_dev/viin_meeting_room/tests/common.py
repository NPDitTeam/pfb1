from datetime import date, datetime

from odoo import fields
from odoo.tests.common import SavepointCase, tagged


class Common(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(Common, cls).setUpClass()
        cls.env.user.tz = 'UTC'
        cls.user_admin = cls.env.ref('base.user_admin')
        cls.user_internal = cls.env.ref('base.user_demo')

        # Meeting Room
        cls.room_1 = cls.env['calendar.meeting.room'].create({
            'name': 'Room 1',
            'location': 'Room 1'
        })
        cls.room_2 = cls.env['calendar.meeting.room'].create({
            'name': 'Room 2',
            'location': 'Room 2'
        })
        cls.room_3 = cls.env['calendar.meeting.room'].create({
            'name': 'Room 3'
        })

        # Calendar Event
        cls.calendar_event_1 = cls.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-29 00:00:00',
            'stop': '2021-09-29 23:59:59',
            'allday': True,
        })
