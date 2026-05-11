from odoo.tests.common import tagged
from odoo.exceptions import UserError

from .common import Common


@tagged('post_install', '-at_install')
class TestMeetingRoom(Common):

    """
    Check for duplicate meeting room bookings: in case the schedule overlaps with different rooms
    """
    def test_01_check_calendar_event(self):
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 09:00:00',
            'room_id': self.room_1.id
        })
        canlendar_event_2 = self.env['calendar.event'].create({
            'name': 'Calendar Event 2',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 09:00:00',
            'room_id': self.room_2.id
        })

    """
    Check for duplicate meeting room bookings: in case the schedule overlaps with same rooms
    """
    def test_01_check_duplicate_calendar_event(self):
        # Event 1:
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:30:00',
            'stop': '2021-09-30 09:00:00',
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 08:00:00',
                'stop': '2021-09-30 09:30:00',
                'room_id': self.room_1.id
            })

    def test_02_check_duplicate_calendar_event(self):
        # Event 1: schedule by hour
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:30:00',
            'stop': '2021-09-30 09:00:00',
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 08:00:00',
                'stop': '2021-09-30 09:45:00',
                'room_id': self.room_1.id
            })

    def test_03_check_duplicate_calendar_event(self):
        # Event 1: schedule by hour
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:30:00',
            'stop': '2021-09-30 09:00:00',
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 08:30:00',
                'stop': '2021-09-30 09:00:00',
                'room_id': self.room_1.id
            })

    def test_04_check_duplicate_calendar_event(self):
        # Event 1: schedule by hour
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:30:00',
            'stop': '2021-09-30 09:00:00',
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour
        canlendar_event_2 = self.env['calendar.event'].create({
            'name': 'Calendar Event 2',
            'start': '2021-09-30 09:00:00',
            'stop': '2021-09-30 09:30:00',
            'room_id': self.room_1.id
        })

    def test_05_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: All Day
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 23:00:00',
                'stop': '2021-09-30 23:59:00',
                'allday': True,
                'room_id': self.room_1.id
            })

    def test_06_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 00:00:00',
                'stop': '2021-09-30 01:00:00',
                'room_id': self.room_1.id
            })

    def test_07_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 23:59:59',
                'stop': '2021-10-01 01:00:00',
                'room_id': self.room_1.id
            })

    def test_08_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour
        canlendar_event_2 = self.env['calendar.event'].create({
            'name': 'Calendar Event 2',
            'start': '2021-10-01 00:00:00',
            'stop': '2021-10-01 01:00:00',
            'room_id': self.room_1.id
        })

    def test_09_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour and repeat by day the number of repetitions is 2
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-29 00:00:00',
                'stop': '2021-09-29 01:00:00',
                'room_id': self.room_1.id,
                'recurrency': True,
                'interval': 1,
                'rrule_type': 'daily',
                'end_type': 'count',
                'count': 2,
            })

    def test_10_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour and repeat by day the number of repetitions is 2, 2 days repeat 1 time
        canlendar_event_2 = self.env['calendar.event'].create({
            'name': 'Calendar Event 2',
            'start': '2021-09-29 00:00:00',
            'stop': '2021-09-29 01:00:00',
            'room_id': self.room_1.id,
            'recurrency': True,
            'interval': 2,
            'rrule_type': 'daily',
            'end_type': 'count',
            'count': 2,
        })

    def test_11_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour and repeat by day the number of repetitions is 2, end type is 'end date'
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-29 00:00:00',
                'stop': '2021-09-29 01:00:00',
                'room_id': self.room_1.id,
                'recurrency': True,
                'interval': 1,
                'rrule_type': 'daily',
                'end_type': 'end_date',
                'until': '2021-09-30'
            })

    def test_12_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour and repeat by week the number of repetitions is 2, do not choose the day of the week
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-23 00:00:00',
                'stop': '2021-09-23 01:00:00',
                'room_id': self.room_1.id,
                'recurrency': True,
                'interval': 1,
                'rrule_type': 'weekly',
                'end_type': 'count',
                'count': 2
            })

    def test_13_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-09-30 08:00:00',
            'stop': '2021-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour and repeat by week the number of repetitions is 2, choose the day of the week is Friday
        canlendar_event_2 = self.env['calendar.event'].create({
            'name': 'Calendar Event 2',
            'start': '2021-09-23 00:00:00',
            'stop': '2021-09-23 01:00:00',
            'room_id': self.room_1.id,
            'recurrency': True,
            'interval': 1,
            'rrule_type': 'weekly',
            'end_type': 'count',
            'count': 2,
            'fr': 1
        })

    def test_14_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2021-10-30 08:00:00',
            'stop': '2021-10-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour and repeat by monthly the number of repetitions is 2, repeat today
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 00:00:00',
                'stop': '2021-09-30 01:00:00',
                'room_id': self.room_1.id,
                'recurrency': True,
                'interval': 1,
                'rrule_type': 'monthly',
                'end_type': 'count',
                'count': 2,
                'month_by': 'date',
                'day': 30
            })

    def test_15_check_duplicate_calendar_event(self):
        # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2022-09-30 08:00:00',
            'stop': '2022-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
        # Envent 2: schedule by hour and repeat by yearly the number of repetitions is 2
        with self.assertRaises(UserError):
            canlendar_event_2 = self.env['calendar.event'].create({
                'name': 'Calendar Event 2',
                'start': '2021-09-30 00:00:00',
                'stop': '2021-09-30 01:00:00',
                'room_id': self.room_1.id,
                'recurrency': True,
                'interval': 1,
                'rrule_type': 'yearly',
                'end_type': 'count',
                'count': 2,
            })
    def test_16_check_duplicate_meeting_room(self):
    # Event 1: All Day
        canlendar_event_1 = self.env['calendar.event'].create({
            'name': 'Calendar Event 1',
            'start': '2022-09-30 08:00:00',
            'stop': '2022-09-30 18:00:00',
            'allday': True,
            'room_id': self.room_1.id
        })
    # Event2: Copy Event 1 but not copy room
        canlendar_event_2 = canlendar_event_1.copy()
        self.assertFalse(canlendar_event_2.room_id)
