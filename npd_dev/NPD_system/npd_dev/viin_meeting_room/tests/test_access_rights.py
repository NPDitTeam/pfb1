from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import Common


@tagged('access_rights')
class TestAccessRights(Common):

    def test_user_internal_access_meeting_room(self):
        """
        Internal users only have permission to read the model 'calendar.meeting.room'
        """
        self.room_1 = self.room_1.with_user(self.user_internal)
        self.room_1.read()
        with self.assertRaises(AccessError):
            meeting_room = self.env['calendar.meeting.room'].with_user(self.user_internal).create({
                'name': 'Room Test'
            })
        with self.assertRaises(AccessError):
            self.room_1.write({'name': 'Room Test'})
        with self.assertRaises(AccessError):
            self.room_1.unlink()

    def test_user_admin_access_meeting_room(self):
        """
        Admin users has all rights to model 'calendar.meeting.room'
        """
        self.room_1 = self.room_1.with_user(self.user_admin)
        self.room_1.read()
        meeting_room = self.env['calendar.meeting.room'].with_user(self.user_admin).create({
            'name': 'Meeting Room',
            'location': 'Meeting Room'
        })
        self.room_1.write({'name': 'Room Test'})
        self.room_1.unlink()
