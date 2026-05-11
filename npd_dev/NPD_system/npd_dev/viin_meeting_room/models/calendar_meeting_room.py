from odoo import models, fields


class MeetingRoom(models.Model):
    _name = 'calendar.meeting.room'
    _description = 'Meeting Room Management'

    name = fields.Char(string='Meeting Room', translate=True, required=True)
    capacity = fields.Integer(string='Capacity')
    location = fields.Char(string='Location')
    active = fields.Boolean(string='Active', default=True, help="If unchecked, it will allow you to hide the meeting room without removing it.")

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(name)',
         "The name of the meeting room must be unique!"),
    ]
