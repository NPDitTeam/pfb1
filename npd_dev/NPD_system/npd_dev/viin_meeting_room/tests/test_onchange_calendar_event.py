from odoo.tests.common import Form, tagged

from .common import Common


@tagged('-at_install', 'post_install')
class TestOnchangeCalendarEvent(Common):

    @classmethod
    def setUpClass(cls):
        super(TestOnchangeCalendarEvent, cls).setUpClass()

    def test_01_check_onchange_calendar_evnet(self):
        # Choose a meeting room with a location setting
        calendar_form = Form(self.env['calendar.event'])
        calendar_form.room_id = self.room_1
        self.assertEqual(calendar_form.location, self.room_1.location)

    def test_02_check_onchange_calendar_evnet(self):
        # Select a meeting room with no location set up
        calendar_form = Form(self.env['calendar.event'])
        calendar_form.room_id = self.room_3
        self.assertFalse(calendar_form.location)

    def test_03_check_onchange_calendar_evnet(self):
        # Select the meeting room with the location setting then delete and leave the meeting room empty
        calendar_event_form_test = Form(self.calendar_event_1)
        calendar_event_form_test.room_id = self.room_2
        self.assertEqual(calendar_event_form_test.location, self.room_2.location)
        calendar_event_form_test.room_id = self.env['calendar.meeting.room']
        self.assertEqual(calendar_event_form_test.location, self.calendar_event_1.location)
