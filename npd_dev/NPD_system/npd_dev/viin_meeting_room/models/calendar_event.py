from datetime import timedelta

from odoo import models, fields , _, api
from odoo.exceptions import  UserError
from odoo.tools.date_utils import start_of, end_of


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    room_id = fields.Many2one('calendar.meeting.room', string='Meeting Room', tracking=True)

    employee_ids = fields.Many2many('res.users', string='Employee Attendees')

    def _prepare_overlap_event_domain(self):
        min_start = start_of(min(self.mapped('start')), 'day')
        max_stop = end_of(max(self.mapped('stop')), 'day')
        return [('room_id', 'in', self.room_id.ids),
                ('start', '<=', max_stop + timedelta(days=1)),
                ('stop', '>=', min_start - timedelta(days=1)),
                '|', ('follow_recurrence', '=', False),
                '&', '&', ('follow_recurrence', '=', True),
                ('recurrency', '=', True),
                ('recurrence_id', '!=', False)]

    @api.returns('self', lambda value:value.id)
    def copy_data(self, default=None):
        if not self._context.get('allow_copy_room', False):
            if default is None:
                default = {}
            default['room_id'] = False
        return super(CalendarEvent, self).copy_data(default)

    def _check_duplicate_room_time(self):
        """
        Check overlapping calendar events with meeting rooms:
        - 2 Calendar Event(hour calendar event type):
            + min(stop) - max(start) => timedelta.days > 0 and timedelta.seconds >0
            => Raise Exception
        - 2 Calendar Event(all day calendar event type):
            => Raise Exception
        - 2 Calendar Event(all day event type and hour event type):
            + Convert all day calendar events to user timezone
            + If the start or end time of the hourly calendar event coincides with the all-day calendar event date
            => Raise Exception
        """
        if not self:
            return
        time_to_tz = self.env['to.base'].convert_utc_time_to_tz
        tz = self._context.get('tz', False)
        to_date = fields.Date.to_date
        events_may_overlap = self.env['calendar.event'].search(self._prepare_overlap_event_domain())
        if not events_may_overlap:
            return
        for r in self.filtered(lambda e: e.room_id and e.active):
            for event in events_may_overlap.filtered(lambda e: e.room_id == r.room_id) - r:
                delta = min(r.stop, event.stop) - max(r.start, event.start)
                if not r.allday and not event.allday and delta.days < 0 or (delta.days == 0 and delta.seconds <= 0):
                    continue
                elif r.allday or event.allday:
                    event_allday, event_rm = (r + event).sorted(lambda r: not r.allday)
                    event_rm_stop = event_rm.stop
                    event_rm_start = event_rm.start
                    if not event_rm.allday:
                        event_rm_stop = time_to_tz(event_rm_stop, tz)
                        event_rm_start = time_to_tz(event_rm_start, tz)
                    if to_date(event_allday.start) > to_date(event_rm_stop) or to_date(event_allday.stop) < to_date(event_rm_start):
                        continue
                raise UserError(_("You may not be able to book the meeting room %(room)s for the event `%(current_event)s`"
                                  " while it is currently booked for the event `%(event)s`. You may shift your event to"
                                  " another time or contact %(owner)s who is the owner of the event `%(event)s` if you"
                                  " want to convince her or him to give you this slot.")
                                  % {
                                      'room': r.room_id.name,
                                      'current_event': r.display_name,
                                      'event': event.display_name,
                                      'owner': event.user_id.name
                                      }
                                  )

    @api.model
    def _get_public_fields(self):
        res = super(CalendarEvent, self)._get_public_fields()
        res.add('room_id')
        return res

    @api.onchange('room_id')
    def _onchange_room_id(self):
        if self.room_id:
            self.location = self.room_id.location
        else:
            self.location = self._origin.location

    @api.model_create_multi
    @api.returns('self', lambda value:value.id)
    def create(self, vals_list):
        rec = super(CalendarEvent, self).create(vals_list)
        rec._check_duplicate_room_time()
        return rec

    def write(self, vals):
        res = super(CalendarEvent, self).write(vals)
        self._check_duplicate_room_time()
        return res
