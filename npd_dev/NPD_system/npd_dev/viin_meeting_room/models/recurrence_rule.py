from odoo import models

class RecurrenceRule(models.Model):
    _inherit = 'calendar.recurrence'

    def _apply_recurrence(self, specific_values_creation=None, no_send_edit=False):
        return super(RecurrenceRule, self.with_context(allow_copy_room=True))._apply_recurrence(specific_values_creation, no_send_edit)
