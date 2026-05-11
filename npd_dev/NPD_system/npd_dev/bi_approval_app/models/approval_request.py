from odoo import api, fields, models, _
from bs4 import BeautifulSoup
import requests
import logging

_logger = logging.getLogger(__name__)

class ApprovalRequest(models.Model):
    _name = "approval.request"
    _inherit = ['mail.thread']
    _description = "Approval Request"

    name = fields.Char(string="Title")
    request_date = fields.Datetime(string="Request Date", default=fields.Datetime.now)
    product_id = fields.Many2one("product.template", string="Item")
    amount = fields.Float(string="Amount")
    approval_name_id = fields.Many2one("approval.type", string="Type", required=True)
    approval_name_type_id = fields.Many2one("approval.name_approval_type", string="Approval Type", required=True)
    payment = fields.Float(string="Payment")
    description = fields.Html(string="Description")
    plain_description = fields.Text(string="Plain Description", compute="_compute_plain_description")
    approver_ids = fields.Many2many('res.users', 'approval_request_approver_rel', string='Approvers', compute='_compute_approvers', store=True)
    approved_ids = fields.Many2many('res.users', 'approval_request_approved_rel', string='Approved Users', readonly=True)
    request_by = fields.Many2one("res.users", string="Request By", default=lambda self: self.env.user, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('submit', 'Submitted'), ('approve', 'Approved'), ('cancel', 'Cancel')],
                             string="Status", default="draft", tracking=True, index=True)
    date_from = fields.Datetime('From Date')
    date_to = fields.Datetime('To Date')
    location = fields.Char(string="Location")
    quality = fields.Char(string="Quality")
    period = fields.Float(string="Period")
    contact_number = fields.Char(string="Contact Number")
    contact_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                      string="Contact Status", default="none", compute="_compute_approval_type_field")
    date_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                   string="Date Status", default="none", compute="_compute_approval_type_field")
    period_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                     string="Period Status", default="none", compute="_compute_approval_type_field")
    item_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                   string="Item Status", default="none", compute="_compute_approval_type_field")
    quality_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                      string="Quality Status", default="none", compute="_compute_approval_type_field")
    amount_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                     string="Amount Status", default="none", compute="_compute_approval_type_field")
    payment_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                      string="Payment Status", default="none", compute="_compute_approval_type_field")
    location_status = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('none', 'None')],
                                       string="Location Status", default="none", compute="_compute_approval_type_field")
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")

    next_approver_id = fields.Many2one("res.users", string="Next Approver", compute="_compute_next_approver", readonly=True)
    pending_approvers_count = fields.Integer(string="Pending Approvers Count", compute="_compute_next_approver", readonly=True)
    is_request_by_current_user = fields.Boolean(string="Is Request By Current User", compute="_compute_is_request_by_current_user")
    is_approved = fields.Boolean("is Approved", default=False, compute='_compute_is_approved')
    last_approver_id = fields.Many2one("res.users", string="Last Approver", readonly=True)
    next_approver_signature = fields.Binary(related='last_approver_id.digital_signature', string="Next Approver Signature", readonly=True)

    @api.depends('description')
    def _compute_plain_description(self):
        for record in self:
            soup = BeautifulSoup(record.description or "", "html.parser")
            record.plain_description = soup.get_text()

    @api.onchange('approval_name_id')
    @api.depends('approval_name_id')
    def _compute_approval_type_field(self):
        for record in self:
            if record.approval_name_id:
                record.contact_status = record.approval_name_id.contact_status
                record.date_status = record.approval_name_id.date_status
                record.period_status = record.approval_name_id.period_status
                record.item_status = record.approval_name_id.item_status
                record.quality_status = record.approval_name_id.quality_status
                record.amount_status = record.approval_name_id.amount_status
                record.payment_status = record.approval_name_id.payment_status
                record.location_status = record.approval_name_id.location_status

    @api.depends('approval_name_id.line_ids')
    def _compute_approvers(self):
        for record in self:
            record.approver_ids = record.approval_name_id.line_ids.mapped('user_id')

    @api.depends('approver_ids', 'approved_ids')
    def _compute_next_approver(self):
        for record in self:
            pending_approvers = record.approver_ids - record.approved_ids
            record.next_approver_id = pending_approvers[0] if pending_approvers else False
            record.pending_approvers_count = len(pending_approvers)

    @api.depends('request_by')
    def _compute_is_request_by_current_user(self):
        for record in self:
            record.is_request_by_current_user = record.request_by.id == self.env.uid

    @api.depends('approved_ids')
    def _compute_is_approved(self):
        for record in self:
            record.is_approved = self.env.user.id in record.approved_ids.ids

    def action_submit(self):
        for record in self:
            record.state = 'submit'
            _logger.info(f'Submitting request {record.name} with ID {record.id}')  # Logging
            self.send_line_notify(record, action='submit')

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'
            _logger.info(f'Cancelling request {record.name} with ID {record.id}')  # Logging
            self.send_line_notify(record, action='cancel')

    def set_draft(self):
        for record in self:
            record.state = 'draft'

    def action_approve(self):
        for record in self:
            if record.approver_ids:
                if self.env.user.has_group('bi_approval_app.group_approval_manager'):
                    record.write({'approved_ids': [(6, 0, record.approver_ids.ids)]})
                elif self.env.user.id in record.approver_ids.ids and self.env.user.id not in record.approved_ids.ids:
                    record.write({'approved_ids': [(4, self.env.user.id, None)]})
                elif self.env.user.id in record.approver_ids.ids and self.env.user.id in record.approved_ids.ids and not set(
                        record.approver_ids.ids) == set(record.approved_ids.ids):
                    raise ValidationError(_('Already approved and waiting for another approvers'))

                # Store the last approver's ID
                record.write({'last_approver_id': self.env.user.id})

                if set(record.approver_ids.ids) == set(record.approved_ids.ids):
                    record.write({'state': 'approve'})
                    _logger.info(f'Approving request {record.name} with ID {record.id}')  # Logging
                    # แจ้งเตือนผ่าน LINE เมื่อสถานะเป็น "approved"
                    self.send_line_notify(record, action='approve')

    def action_refuse(self):
        for record in self:
            record.state = 'draft'
            record.approved_ids = [(5, 0, 0)]  # Clear the approved users
            record.is_approved = False  # Set is_approved to False
            _logger.info(f'Refusing request {record.name} with ID {record.id}')  # Logging
            self.send_line_notify(record, action='refuse')

    def send_line_notify(self, record, action):
        url = "https://notify-api.line.me/api/notify"
        state_color = {
            'draft': '🔵 Draft',
            'submit': '🟡 Submitted',
            'approve': '🟢 Approved',
            'cancel': '🔴 Canceled'
        }

        plain_description = BeautifulSoup(record.description or "", "html.parser").get_text()
        colored_state = state_color.get(record.state, 'Unknown')

        if action == 'approve':
            message = (
                f"📄 **คำขอการอนุมัติ**: {record.name}\n"
                f"👤 **ผู้ขออนุมัติ**: {record.request_by.name}\n"
                f"🔍 **รายละเอียด**: {plain_description}\n"
                f"⚙️ **สถานะ**: {colored_state}\n"
                f"👤 **ผู้อนุมัติสุดท้าย**: {self.env.user.name}\n"
            )
        elif action == 'refuse':
            approvers = record.approval_name_id.line_ids.mapped('user_id')
            message = (
                f"📄 **คำขอการอนุมัติ**: {record.name}\n"
                f"👤 **ผู้ขออนุมัติ**: {record.request_by.name}\n"
                f"🔍 **รายละเอียด**: {plain_description}\n"
                f"✅ **ผู้อนุมัติ**: {', '.join(approvers.mapped('name'))}\n"
                f"⚙️ **สถานะ**: {colored_state}\n"
                f"❌ **ให้ปรับแก้ไขโดย**: {self.env.user.name}\n"
            )
        elif action == 'submit':
            approvers = record.approval_name_id.line_ids.mapped('user_id')
            message = (
                f"📄 **คำขอการอนุมัติ**: {record.name}\n"
                f"👤 **ผู้ขออนุมัติ**: {record.request_by.name}\n"
                f"📅 **วันที่ขอ**: {record.request_date}\n"
                f"📝 **ประเภทการอนุมัติ**: {record.approval_name_type_id.name}\n"
                f"🔍 **รายละเอียด**: {plain_description}\n"
                f"✅ **ผู้อนุมัติ**: {', '.join(approvers.mapped('name'))}\n"
                f"⚙️ **สถานะ**: {colored_state}"
            )

        request_by_user = record.request_by
        if request_by_user and request_by_user.line_token:
            headers = {
                "Authorization": "Bearer " + request_by_user.line_token,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            payload = {'message': message}

            _logger.info(f'Sending LINE notification to {request_by_user.name} with headers: {headers} and payload: {payload}')

            response = requests.post(url, headers=headers, data=payload)

            _logger.info(f'LINE API response status code: {response.status_code}')
            _logger.info(f'LINE API response text: {response.text}')

            if response.status_code == 200:
                _logger.info(f'LINE notification sent successfully to {request_by_user.name}. Response: {response.text}')
            else:
                _logger.error(f'Failed to send LINE notification to {request_by_user.name}. Response: {response.text}')

            if action != 'approve':
                for approver in approvers:
                    if approver.line_token:
                        approver_headers = {
                            "Authorization": "Bearer " + approver.line_token,
                            "Content-Type": "application/x-www-form-urlencoded"
                        }
                        _logger.info(f'Approver: {approver.name}, Token: {approver.line_token}')
                        approver_response = requests.post(url, headers=approver_headers, data=payload)
                        _logger.info(f'LINE API response for approver {approver.name}: {approver_response.text}')
