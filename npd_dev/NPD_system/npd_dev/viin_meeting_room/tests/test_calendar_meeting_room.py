from psycopg2 import IntegrityError

from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .common import Common


@tagged('-at_install', 'post_install')
class TestCalendarMeetingRoom(Common):

    @mute_logger('odoo.sql_db')
    def test_01_constrains_meeting_room(self):
        # Duplicate meeting room
        with self.assertRaises(IntegrityError):
            self.room_1.copy()

    @mute_logger('odoo.sql_db')
    def test_02_constrains_meeting_room(self):
        # Create a meeting room with the same name as an existing meeting room
        with self.assertRaises(IntegrityError):
            meeting_room = self.env['calendar.meeting.room'].create({
                'name': 'Room 1'
            })

    @mute_logger('odoo.sql_db')
    def test_03_constrains_meeting_room(self):
        # Edit the meeting room name to be the same as another meeting room name
        with self.assertRaises(IntegrityError):
            self.room_2.write({'name': 'Room 1'})
            self.room_2.flush()

    @mute_logger('odoo.sql_db')
    def test_04_constrains_meeting_room(self):
        # Archive the meeting room, create a new meeting room with the same name as the old meeting room
        self.room_1.action_archive()
        self.assertFalse(self.room_1.active)
        with self.assertRaises(IntegrityError):
            meeting_room = self.env['calendar.meeting.room'].create({
                'name': 'Room 1'
            })
