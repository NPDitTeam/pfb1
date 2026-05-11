# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ApprovalType(models.Model):
    _name = "approval.type"
    _inherit = ['mail.thread']
    _description = "Approval Type"

    name = fields.Char(string="Name", required=True)
    description = fields.Char(string="Description")
    approval_image = fields.Image(string="Approval Image")
    contact_status = fields.Selection([('required', 'Required'),
                                       ('optional', 'Optional'), ('none', 'None')], string="Contact",
                                      default="none")
    date_status = fields.Selection([('required', 'Required'),
                                    ('optional', 'Optional'), ('none', 'None')], string="Date",
                                   default="none")
    period_status = fields.Selection([('required', 'Required'),
                                      ('optional', 'Optional'), ('none', 'None')], string="Period",
                                     default="none")
    item_status = fields.Selection([('required', 'Required'),
                                    ('optional', 'Optional'), ('none', 'None')], string="Item",
                                   default="none")
    quality_status = fields.Selection([('required', 'Required'),
                                       ('optional', 'Optional'), ('none', 'None')], string="Quality",
                                      default="none")
    amount_status = fields.Selection([('required', 'Required'),
                                      ('optional', 'Optional'), ('none', 'None')], string="Amount",
                                     default="none")
    payment_status = fields.Selection([('required', 'Required'),
                                       ('optional', 'Optional'), ('none', 'None')], string="Payment",
                                      default="none")
    location_status = fields.Selection([('required', 'Required'),
                                        ('optional', 'Optional'), ('none', 'None')], string="Location",
                                       default="none")
    minimum_approvers = fields.Integer(
        string="Minimum Approvers", compute="_get_lines")
    line_ids = fields.One2many(
        "multi.approval_type.line", "approval_type_id", string="Approval Line")
    is_user_enable = fields.Boolean(
        string="Is User Enable", compute="_compute_user_enable")
    is_apply_for_model = fields.Boolean(string="Apply For Model?")
    is_mail_notification = fields.Boolean(string="Mail Notification")
    template_request_id = fields.Many2one(
        "mail.template", string="Template For The Request")
    template_approve_id = fields.Many2one(
        "mail.template", string="Template Of 'Approved' Case")
    template_refuse_id = fields.Many2one(
        "mail.template", string="Template Of 'Refused' Case")

    @api.onchange('is_apply_for_model')
    def _onchange_is_apply_for_model(self):
        if self.is_apply_for_model:
            self.template_request_id = template = self.env.ref(
                'bi_approval_app.email_template_approval_request').id
            self.template_approve_id = self.env.ref(
                'bi_approval_app.email_template_approval_approved').id
            self.template_refuse_id = template = self.env.ref(
                'bi_approval_app.email_template_approval_refuse').id

    @api.depends('line_ids.user_id', 'line_ids')
    def _compute_user_enable(self):
        for line in self:
            if self.env.user.has_group('bi_approval_app.group_approval_type_button'):
                line.sudo().write({'is_user_enable': True})
            else:
                line.sudo().write({'is_user_enable': False})

    def _get_lines(self):
        for line in self:
            line.minimum_approvers = self.env['multi.approval_type.line'].search_count(
                [('approval_type_id', '=', line.id)])


class MultiApprovalLine(models.Model):
    _name = "multi.approval_type.line"
    _description = "Multi Approval Line"

    approval_type_id = fields.Many2one("approval.type", string="Approval Type")
    title = fields.Char(string="Title", required=True)
    user_id = fields.Many2one("res.users", string="User", required=True)
    type_of_approval = fields.Selection([('required', 'Required')], string="Type Of Approval",
                                        default="required")
