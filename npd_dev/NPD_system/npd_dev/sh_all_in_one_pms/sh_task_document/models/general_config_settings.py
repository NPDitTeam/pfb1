# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_task_expiry_notification = fields.Boolean("Expiry Notification")
    sh_task_is_notify_customer = fields.Boolean("Notify Customer")
    sh_task_on_date_notify = fields.Boolean("On Date Notification")
    task_enter_before_first_notify = fields.Integer(
        "Notify Before Expiry Date")
    task_enter_before_second_notify = fields.Integer(
        "Notify Before Expiry Date")
    task_enter_before_third_notify = fields.Integer(
        "Notify Before Expiry Date")
    task_enter_after_first_notify = fields.Integer(
        "Notify After Expiry Date")
    task_enter_after_second_notify = fields.Integer(
        "Notify After Expiry Date")
    task_enter_after_third_notify = fields.Integer(
        "Notify After Expiry Date")
    task_attachment_email = fields.Char("Email to")

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    sh_task_expiry_notification = fields.Boolean(
        string="Expiry Notification", related='company_id.sh_task_expiry_notification', readonly=False)
    sh_task_is_notify_customer = fields.Boolean(
        string="Notify Customer", related='company_id.sh_task_is_notify_customer', readonly=False)
    sh_task_on_date_notify = fields.Boolean(
        string="On Date Notification", related='company_id.sh_task_on_date_notify', readonly=False)
    task_enter_before_first_notify = fields.Integer(
        "Notify Before Expiry Date", related='company_id.task_enter_before_first_notify', readonly=False)
    task_enter_before_second_notify = fields.Integer(
        "Notify Before Expiry Date", related='company_id.task_enter_before_second_notify', readonly=False)
    task_enter_before_third_notify = fields.Integer(
        string="Notify Before Expiry Date", related='company_id.task_enter_before_third_notify', readonly=False)
    task_enter_after_first_notify = fields.Integer(
        string="Notify After Expiry Date", related='company_id.task_enter_after_first_notify', readonly=False)
    task_enter_after_second_notify = fields.Integer(
        string="Notify After Expiry Date", related='company_id.task_enter_after_second_notify', readonly=False)
    task_enter_after_third_notify = fields.Integer(
        string="Notify After Expiry Date", related='company_id.task_enter_after_third_notify', readonly=False)
    task_attachment_email = fields.Char(string="Email to", related='company_id.task_attachment_email', readonly=False)
