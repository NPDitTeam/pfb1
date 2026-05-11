# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import api, fields, models, _
from datetime import datetime


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    approval_level_id = fields.Many2one(
        'sh.payroll.approval.config', string="Approval Level", compute="compute_approval_level")
    state = fields.Selection(
        selection_add=[('waiting_for_approval', 'Waiting for Approval')])
    level = fields.Integer(string="Next Approval Level", readonly=True)
    user_ids = fields.Many2many('res.users', string="Users", readonly=True)
    group_ids = fields.Many2many('res.groups', string="Groups", readonly=True)
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search="_search_is_boolean")
    approval_info_line = fields.One2many(
        'sh.approval.info', 'hr_payslip_id', readonly=True)
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)
    user_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True)
    net_amount = fields.Float(compute="compute_approval_level")

    def compute_is_boolean(self):
        
        if self.env.uid in self.user_ids.ids or any(item in self.env.user.groups_id.ids for item in self.group_ids.ids):
            self.is_boolean = True
        else:
            self.is_boolean = False

    def _search_is_boolean(self, operator, value):
        results = []

        if value:
            payslip_ids = self.env['hr.payslip'].search([])
            if payslip_ids:
                for payslip_id in payslip_ids:
                    if self.env.uid in payslip_id.user_ids.ids or any(item in self.env.user.groups_id.ids for item in payslip_id.group_ids.ids):
                        results.append(payslip_id.id)
        return [('id', 'in', results)]

    def action_payslip_done(self):

        super(HrPayslip, self).action_payslip_done()

        if self.env.user.has_group('sh_all_in_one_hrms.group_enable_sh_payslip_dynamic_approval'):

            template_id = self.env.ref(
                "sh_all_in_one_hrms.email_template_for_approve_hr_payslip")

            self.approval_info_line = False
            self.level = False
            self.group_ids = [(6, 0, [])]
            self.user_ids = [(6, 0, [])]
            self.rejection_date = False
            self.reject_reason = False
            self.reject_by = False

            if self.approval_level_id.payroll_approval_line:
                self.write({
                    'state': 'waiting_for_approval'
                })
                lines = self.approval_level_id.payroll_approval_line

                for line in lines:
                    dictt = []
                    if line.approve_by == 'group':
                        dictt.append((0, 0, {
                            'level': line.level,
                            'user_ids': [(6, 0, [])],
                            'group_ids': [(6, 0, line.group_ids.ids)],
                        }))

                    if line.approve_by == 'user':
                        dictt.append((0, 0, {
                            'level': line.level,
                            'user_ids': [(6, 0, line.user_ids.ids)],
                            'group_ids': [(6, 0, [])],
                        }))

                    self.update({
                        'approval_info_line': dictt
                    })

                if lines[0].approve_by == 'group':
                    self.write({
                        'level': lines[0].level,
                        'group_ids': [(6, 0, lines[0].group_ids.ids)],
                        'user_ids': [(6, 0, [])]
                    })

                    users = self.env['res.users'].search(
                        [('groups_id', 'in', lines[0].group_ids.ids)])

                    if template_id and users:
                        for user in users:
                            template_id.sudo().send_mail(self.id, force_send=True, email_values={
                                'email_from': self.env.user.email, 'email_to': user.email})

                    notifications = []
                    if users:
                        for user in users:
                            notifications.append([
                                (self._cr.dbname, 'res.partner', user.partner_id.id),
                                {'type': 'user_connection', 'title': _(
                                    'Notitification'), 'message': 'You have approval notification for Payslip %s' % (self.name), 'sticky': True, 'warning': True}])
                        self.env['bus.bus'].sendmany(notifications)

                if lines[0].approve_by == 'user':
                    self.write({
                        'level': lines[0].level,
                        'user_ids': [(6, 0, lines[0].user_ids.ids)],
                        'group_ids': [(6, 0, [])]
                    })

                    if template_id and lines[0].user_ids:
                        for user in lines[0].user_ids:
                            template_id.sudo().send_mail(self.id, force_send=True, email_values={
                                'email_from': self.env.user.email, 'email_to': user.email})

                    notifications = []
                    if lines[0].user_ids:
                        for user in lines[0].user_ids:
                            notifications.append([
                                (self._cr.dbname, 'res.partner', user.partner_id.id),
                                {'type': 'user_connection', 'title': _(
                                    'Notitification'), 'message': 'You have approval notification for Payslip %s' % (self.name), 'sticky': True, 'warning': True}])
                        self.env['bus.bus'].sendmany(notifications)

            else:
                super(HrPayslip, self).action_payslip_done()

    @api.depends('line_ids.total')
    def compute_approval_level(self):

        line_with_code_net = self.line_ids.filtered(lambda x: x.code == 'NET')

        if line_with_code_net:

            self.net_amount = line_with_code_net[0].total
            payroll_approvals = self.env['sh.payroll.approval.config'].search(
                [('min_amount', '<', line_with_code_net[0].total), ('company_ids.id', 'in', [self.env.user.company_id.id])])

            listt = []
            for payroll_approval in payroll_approvals:
                listt.append(payroll_approval.min_amount)

            if listt:
                payroll_approval = payroll_approvals.filtered(
                    lambda x: x.min_amount == max(listt))

                self.update({
                    'approval_level_id': payroll_approval[0].id
                })
            else:

                self.approval_level_id = False
        else:
            self.net_amount = False
            self.approval_level_id = False

    def action_approve_payslip(self):

        template_id = self.env.ref(
            "sh_all_in_one_hrms.email_template_for_approve_hr_payslip")

        info = self.approval_info_line.filtered(
            lambda x: x.level == self.level)

        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        line_id = self.env['sh.payroll.approval.line'].search(
            [('payroll_approval_config_id', '=', self.approval_level_id.id), ('level', '=', self.level)])

        next_line = self.env['sh.payroll.approval.line'].search(
            [('payroll_approval_config_id', '=', self.approval_level_id.id), ('id', '>', line_id.id)], limit=1)

        if next_line:
            if next_line.approve_by == 'group':
                self.write({
                    'level': next_line.level,
                    'group_ids': [(6, 0, next_line.group_ids.ids)],
                    'user_ids': [(6, 0, [])]
                })
                users = self.env['res.users'].search(
                    [('groups_id', 'in', next_line.group_ids.ids)])

                if template_id and users and self.approval_level_id.is_boolean:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.user_id.email + ',' + self.employee_id.work_email})

                if template_id and users and not self.approval_level_id.is_boolean:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if users:
                    for user in users:
                        notifications.append([
                            (self._cr.dbname, 'res.partner', user.partner_id.id),
                            {'type': 'user_connection', 'title': _(
                                'Notitification'), 'message': 'You have approval notification for Payslip %s' % (self.name), 'sticky': True, 'warning': True}])
                    self.env['bus.bus'].sendmany(notifications)

            if next_line.approve_by == 'user':
                self.write({
                    'level': next_line.level,
                    'user_ids': [(6, 0, next_line.user_ids.ids)],
                    'group_ids': [(6, 0, [])]
                })

                if template_id and next_line.user_ids and self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.user_id.email + ',' + self.employee_id.work_email})

                if template_id and next_line.user_ids and not self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if next_line.user_ids:
                    for user in next_line.user_ids:
                        notifications.append([
                            (self._cr.dbname, 'res.partner', user.partner_id.id),
                            {'type': 'user_connection', 'title': _(
                                'Notitification'), 'message': 'You have approval notification for Payslip %s' % (self.name), 'sticky': True, 'warning': True}])
                    self.env['bus.bus'].sendmany(notifications)

        else:
            template_id = self.env.ref(
                "sh_all_in_one_hrms.email_template_for_confirm_hr_payslip")
            if template_id:
                template_id.sudo().send_mail(self.id, force_send=True, email_values={
                    'email_from': self.env.user.email, 'email_to': self.user_id.email})

            notifications = []
            if self.user_id:
                notifications.append([
                    (self._cr.dbname, 'res.partner', self.user_id.partner_id.id),
                    {'type': 'user_connection', 'title': _(
                        'Notitification'), 'message': 'Dear User!! The Payslip %s you created has been confirmed' % (self.name), 'sticky': True, 'warning': True}])
                self.env['bus.bus'].sendmany(notifications)

            self.write({
                'level': False,
                'group_ids': [(6, 0, [])],
                'user_ids': [(6, 0, [])],

            })
            super(HrPayslip, self).action_payslip_done()
