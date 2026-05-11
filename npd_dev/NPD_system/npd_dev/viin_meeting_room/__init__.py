from odoo import api, SUPERUSER_ID
from . import models


def repalce_email_template(env, type):
    invitation_template = env.ref('calendar.calendar_template_meeting_invitation', raise_if_not_found=False)
    changedate_template = env.ref('calendar.calendar_template_meeting_changedate', raise_if_not_found=False)
    reminder_template = env.ref('calendar.calendar_template_meeting_reminder', raise_if_not_found=False)

    str_first = '% if object.event_id.description :'
    str_last = """
        % if object.event_id.room_id :
        <li>Meeting room: ${object.event_id.room_id.name}</li>
        % endif
        % if object.event_id.description :
    """

    if type == "post":
        if invitation_template:
            invitation_template.body_html = invitation_template.body_html.replace(str_first, str_last)
        if changedate_template:
            changedate_template.body_html = changedate_template.body_html.replace(str_first, str_last)
        if reminder_template:
            reminder_template.body_html = reminder_template.body_html.replace(str_first, str_last)
    else:
        if invitation_template:
            invitation_template.body_html = invitation_template.body_html.replace(str_last, str_first)
        if changedate_template:
            changedate_template.body_html = changedate_template.body_html.replace(str_last, str_first)
        if reminder_template:
            reminder_template.body_html = reminder_template.body_html.replace(str_last, str_first)

def post_init_hook(cr, registry):
    """Add information of the meeting room to mail template"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    repalce_email_template(env, 'post')

def uninstall_hook(cr, registry):
    """Remove information of the meeting room from mail template"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    repalce_email_template(env, 'uninstall')
