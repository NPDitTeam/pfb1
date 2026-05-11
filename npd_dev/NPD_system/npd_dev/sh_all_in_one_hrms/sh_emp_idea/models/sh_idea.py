# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import api, fields, models


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_sh_idea = fields.Boolean(
        "Enable Employee Idea Management", implied_group='sh_all_in_one_hrms.group_enable_sh_idea')

# sh.idea object


class ShIdeaCategories(models.Model):
    _name = 'sh.idea'
    _description = 'Idea'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Idea Name', readonly=True,
                       required=True, copy=False, default='New')
    subject = fields.Char(string="Subject")
    idea_category = fields.Many2one(
        'sh.idea.categories', string="Idea Category")
    create_date = fields.Date(required=True, default=lambda self: self._context.get(
        'Created On', fields.Date.context_today(self)))
    created_by = fields.Many2one(
        'res.users', default=lambda self: self.env.uid, string="Created By")
    resp_persons = fields.Many2many(
        'res.users', string="Responsible Persons", compute="_compute_responsible_per", store=True)
    description = fields.Text('Description')
    state = fields.Selection([
        ('new', 'New'),
        ('waiting', 'Waiting For Approval'),
        ('approve', 'Approved'),
        ('refused', 'Refused'),
        ('closed', 'Closed')], string='State', readonly=True, index=True, copy=False, default='new',)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    is_approve = fields.Boolean(compute="_compute_approve_buttont_check")
    approved_by = fields.Many2one('res.users', string="Responsible Person")
    refused_by = fields.Many2one('res.users', string="Responsible Person")
    refused_comment = fields.Text(string="Refused Comment")
    approved_comment = fields.Text(string="Approved Comment")
    rating = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'Minimum'),
        ('3', 'High'),
        ('4', 'Maximum'),
        ('5', 'Max'),
    ], string="Rating")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'sh.idea') or 'New'
            result = super(ShIdeaCategories, self).create(vals)
        return result

    @api.depends('idea_category')
    def _compute_responsible_per(self):
        for rec in self:
            rec.resp_persons = False
            if rec.idea_category:
                rec.resp_persons = [
                    (6, 0, rec.idea_category.responsible_persons.ids)]

    @api.depends('created_by')
    def _compute_approve_buttont_check(self):
        self.is_approve = False
        if self.created_by.id == self.env.user.id:
            self.is_approve = True

    # Idea form button actions
    def new_idea_button(self):
        self.write({'state': 'waiting'})
        template = self.env.ref(
            'sh_all_in_one_hrms.send_new_idea_notification_responsible_user')
        partner_to = ''
        total_receipients = len(self.resp_persons)
        count = 1
        if self.resp_persons:
            for resp in self.resp_persons:
                partner_to += str(resp.partner_id.id)
                if count < total_receipients:
                    partner_to += ','
                count += 1

        template.partner_to = partner_to
        template.send_mail(self.id, force_send=True,
                           notif_layout='mail.mail_notification_light')

    def approve_button(self):
        self.write({'state': 'approve'})
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.idea.approve.wizard',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'current_id': self.id}
        }

    def refuse_button(self):
        self.write({'state': 'refused'})
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.idea.refuse.wizard',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'current_id': self.id}
        }

    def close_button(self):
        self.write({'state': 'closed'})
        return {}

    def reset_to_draft_button(self):
        self.write({'state': 'new'})
        return {}
