from odoo import api, fields, models


class MailActivityMixin(models.AbstractModel):
    _inherit = 'mail.activity.mixin'

    my_activity_date_deadline = fields.Date(
        'My Activity Deadline',
        compute='_compute_my_activity_date_deadline',
        search='_search_my_activity_date_deadline',
        compute_sudo=False,
        readonly=True,
        groups="base.group_user",
    )

    @api.depends('activity_ids.date_deadline', 'activity_ids.user_id')
    def _compute_my_activity_date_deadline(self):
        for record in self:
            record.my_activity_date_deadline = next((
                activity.date_deadline
                for activity in record.activity_ids
                if activity.user_id == self.env.user
            ), False)

    def _search_my_activity_date_deadline(self, operator, operand):
        activity_ids = self.env['mail.activity']._search([
            ('date_deadline', operator, operand),
            ('res_model', '=', self._name),
            ('user_id', '=', self.env.user.id),
        ])
        return [('activity_ids', 'in', activity_ids)]
