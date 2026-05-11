# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import api, fields, models

# Sh Resignation object


class ShResignation(models.Model):
    _name = 'sh.hr.resignation'
    _description = 'Resignation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Resignation Sequence', readonly=True,
                       required=True, copy=False, default='New')
    sh_department_id = fields.Many2one(
        "hr.department", string="Department", store=True)

    sh_contract_id = fields.Many2one(
        'hr.contract', string="Contract", store=True, compute="_sh_compute_current_contract", readonly=False)
    sh_resignation_type = fields.Many2one(
        'sh.resignation.types', string="Types of Resignation")
    description = fields.Text('Description')

    sh_employee_id = fields.Many2one(
        'hr.employee', default=lambda self: self.env.user.employee_id.id, string="Employee", store=True, readonly=True)

    created_by = fields.Many2one(
        'res.users', default=lambda self: self.env.uid, string="Created By")
    approved_by = fields.Many2one('res.users', string="Responsible Person ")
    refused_by = fields.Many2one('res.users', string="Responsible Person")
    refused_comment = fields.Text(string="Refused Comment")
    approved_comment = fields.Text(string="Approved Comment")

    first_contract_start_date = fields.Date(
        "Contract Start Date")
    first_contract_end_date = fields.Date(
        "Contract End Date")

    sh_responsible_person = fields.Many2one(
        related="sh_department_id.manager_id.user_id", string="Responsible Persons", store=True)

    state = fields.Selection([
        ('new', 'New'),
        ('waiting', 'Waiting For Approval'),
        ('approve', 'Approved'),
        ('refused', 'Refused'),
        ('closed', 'Closed')], string='State', readonly=True, index=True, copy=False, default='new',)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    is_approve = fields.Boolean(compute="_compute_approve_buttont_check")

    @api.depends('sh_employee_id')
    def _sh_compute_current_contract(self):
        for rec in self:
            rec.sh_department_id = False
            rec.sh_contract_id = False

            if rec.sh_employee_id and rec.sh_employee_id.department_id:
                rec.sh_department_id = rec.sh_employee_id.department_id
            if rec.sh_employee_id and rec.sh_employee_id.sudo().contract_id:
                rec.sh_contract_id = rec.sh_employee_id.sudo().contract_id

    @api.onchange('sh_contract_id')
    def onchange_sh_contract_id(self):
        self.first_contract_start_date = False
        self.first_contract_end_date = False
        if self.sh_contract_id or self.sh_contract_id.sudo().date_start or self.sh_contract_id.sudo().date_end:
            self.first_contract_start_date = self.sh_contract_id.sudo().date_start
            self.first_contract_end_date = self.sh_contract_id.sudo().date_end

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sh.hr.resignation') or 'New'
                result = super(ShResignation, self).create(vals_list)
        return result

    @api.depends('created_by')
    def _compute_approve_buttont_check(self):
        self.is_approve = False
        if self.created_by.id == self.env.user.id:
            self.is_approve = True

    # Disciplinary form button actions
    def new_resignation_button(self):
        self.write({'state': 'waiting'})
        template = self.env.ref(
            'sh_all_in_one_hrms.send_new_resignation_notification_responsible_user')

        partner_to = ''
        total_receipients = len(self.sh_responsible_person)
        count = 1
        if self.sh_responsible_person:
            for resp in self.sh_responsible_person:
                partner_to += str(resp.partner_id.id)
                if count < total_receipients:
                    partner_to += ','
                count += 1

        template.partner_to = partner_to
        template.send_mail(self.id, force_send=True,
                           notif_layout='mail.mail_notification_light')

    def approve_button(self):
        return {
            'name': 'Resignation Approve',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.resignation.approve.wizard',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'current_id': self.id}
        }

    def refuse_button(self):
        return {
            'name': 'Resignation Refuse',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.resignation.refuse.wizard',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'current_id': self.id}
        }

    def close_button(self):
        self.write({'state': 'closed'})
        return {}

    def reset_to_draft_button(self):
        self.write({'state': 'new',
                    'refused_comment': '',
                    'refused_by': False,
                    'approved_comment': '',
                    'approved_by': False,
                    })
        return {}
