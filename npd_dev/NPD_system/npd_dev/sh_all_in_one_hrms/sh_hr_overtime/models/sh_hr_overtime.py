# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError

# Sh Hr Overtime object


class ShHrOvertime(models.Model):
    _name = 'sh.hr.overtime'
    _description = 'Hr Overtime'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_employee(self):
        return self.env.user.employee_id

    name = fields.Char(string='Reference', readonly=True,
                       required=True, copy=False, default='New')
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  ondelete='cascade', default=_default_employee, required=True, index=True)
    from_hrs = fields.Datetime(string='From')
    to_hrs = fields.Datetime(string='To')
    total_hours = fields.Float(
        string='Hours', compute="_compute_get_total_hours_duration")
    ot_type_id = fields.Many2one('sh.ot.types', string="Overtime Type")
    reject_comment = fields.Text("Comments")
    state = fields.Selection([
        ('new', 'New'),
        ('request', 'Request'),
        ('approve', 'Approved'),
        ('reject', 'Reject')], string='State', readonly=True, index=True, copy=False, default='new',)
    is_approve = fields.Boolean(compute="_compute_approve_buttont_check")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.depends('employee_id')
    def _compute_approve_buttont_check(self):
        self.is_approve = False
        if self.employee_id.user_id.id == self.env.user.id:
            self.is_approve = True

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'sh.hr.overtime') or 'New'
            result = super(ShHrOvertime, self).create(vals)
        return result

    @api.depends('from_hrs', 'to_hrs')
    def _compute_get_total_hours_duration(self):
        """ Get the duration value between the 2 given dates. """
        for record in self:
            record.total_hours = False
            if record.to_hrs and record.from_hrs:
                diff = fields.Datetime.from_string(
                    record.to_hrs) - fields.Datetime.from_string(record.from_hrs)
                if diff:
                    duration = float(diff.days) * 24 + \
                        (float(diff.seconds) / 3600)
                    record.total_hours = round(duration, 2)
            else:
                record.total_hours = False

    @api.constrains('from_hrs', 'to_hrs')
    def _check_validity_constrain(self):
        """ verifies if record.to_hrs is earlier than record.from_hrs. """
        for record in self:
            if record.to_hrs and record.from_hrs:
                if record.to_hrs < record.from_hrs:
                    raise exceptions.ValidationError(
                        _('To date is not greater than From Date !'))

    # Sh Hr Overtime form button actions
    def confirm_button(self):
        self.write({'state': 'request'})
        if not self.employee_id.parent_id:
            raise UserError(_("Please set Manager in employee !"))

        template = self.env.ref(
            'sh_all_in_one_hrms.send_new_overtime_request_notification')
        template.sudo().send_mail(self.id, force_send=True,
                                  notif_layout='mail.mail_notification_light')

    def approve_button(self):
        self.write({'state': 'approve'})
        template = self.env.ref(
            'sh_all_in_one_hrms.send_overtime_request_approved_notification')
        template.sudo().send_mail(self.id, force_send=True,
                                  notif_layout='mail.mail_notification_light')

    def reject_button(self):
        self.write({'state': 'reject'})
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.ot.reject.wizard',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'current_id': self.id}
        }
