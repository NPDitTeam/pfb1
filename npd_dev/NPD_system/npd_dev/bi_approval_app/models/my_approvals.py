from odoo import api, fields, models, _
from bs4 import BeautifulSoup
import requests

class MyApproval(models.Model):
    _name = "my.approval"
    _inherit = ['mail.thread']
    _description = "My Approval"

    name = fields.Char(string="Title", readonly=True)
    request_date = fields.Datetime(string="Request Date", readonly=True)
    product_id = fields.Many2one("product.template", string="Item", readonly=True)
    approved_ids = fields.Many2many("res.users", 'my_approvaled_ref_user_id', string="Approved Users")
    approval_name_id = fields.Many2one("approval.type", string="Type", readonly=True)
    approval_name_type_id = fields.Many2one("approval.name_approval_type", string="Approval Type", readonly=True)
    payment = fields.Float(string="Payment", readonly=True)
    description = fields.Html(string="Description")
    plain_description = fields.Text(string="Plain Description", compute="_compute_plain_description")
    request_by = fields.Many2one("res.users", string="Request By", readonly=True)
    request_id = fields.Many2one('approval.request', string='Request')
    user_ids = fields.Many2many("res.users", string="Approvers", readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('submit', 'Submitted'), ('approve', 'Approved'), ('cancel', 'Cancel')], string="Status", default="draft", tracking=True, index=True)
    is_approved = fields.Boolean("is Approved", default=False, compute='_compute_is_approved')
    next_approver_id = fields.Many2one("res.users", string="Next Approver", compute="_compute_next_approver", readonly=True)
    pending_approvers_count = fields.Integer(string="Pending Approvers Count", compute="_compute_next_approver", readonly=True)
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments", readonly=True)

    last_approver_id = fields.Many2one("res.users", string="Last Approver", readonly=True)
    next_approver_signature = fields.Binary(related='last_approver_id.digital_signature', string="Next Approver Signature", readonly=True)

    @api.depends('description')
    def _compute_plain_description(self):
        for record in self:
            soup = BeautifulSoup(record.description or "", "html.parser")
            record.plain_description = soup.get_text()

    @api.depends('user_ids', 'approved_ids')
    def _compute_next_approver(self):
        for record in self:
            pending_approvers = record.user_ids - record.approved_ids
            record.next_approver_id = pending_approvers[0] if pending_approvers else False
            record.pending_approvers_count = len(pending_approvers)

    @api.depends('approved_ids')
    def _compute_is_approved(self):
        for record in self:
            record.is_approved = self.env.user.id in record.approved_ids.ids

    @api.onchange('approval_name_id')
    def _onchange_approval_name_id(self):
        for record in self:
            if record.approval_name_id and record.approval_name_id.line_ids:
                record.write({'user_ids': [(4, i) for i in record.approval_name_id.line_ids.mapped('user_id').ids]})
            if record.approval_name_id and not record.approval_name_id.line_ids:
                record.write({'user_ids': False})

    def action_approve(self):
        for record in self:
            if record.user_ids:
                if self.env.user.has_group('bi_approval_app.group_approval_manager'):
                    record.write({'approved_ids': [(6, 0, record.user_ids.ids)]})
                elif self.env.user.id in record.user_ids.ids and self.env.user.id not in record.approved_ids.ids:
                    record.write({'approved_ids': [(4, self.env.user.id, None)]})
                elif self.env.user.id in record.user_ids.ids and self.env.user.id in record.approved_ids.ids and not set(record.user_ids.ids) == set(record.approved_ids.ids):
                    raise ValidationError(_('Already approved and waiting for another approvers'))

                # Store the last approver's ID
                record.write({'last_approver_id': self.env.user.id})

                if set(record.user_ids.ids) == set(record.approved_ids.ids):
                    record.write({'state': 'approve'})
                    if record.request_id:
                        record.request_id.sudo().write({'state': 'approve'})
                    # แจ้งเตือนผ่าน LINE เมื่อสถานะเป็น "approved"
                    self.send_line_notify(record, is_approved=True)

    def action_refuse(self):
        for record in self:
            record.state = 'draft'
            final_dict = {'state': 'draft'}
            record.request_id.sudo().write(final_dict)
            # แจ้งเตือนผ่าน LINE เมื่อสถานะเป็น "cancel"
            # self.send_line_notify(record, is_approved=False)

    def send_line_notify(self, record, is_approved):
        # ฟังก์ชันการส่งแจ้งเตือน
        def send_notify(token, message):
            url = "https://notify-api.line.me/api/notify"
            headers = {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            payload = {'message': message}
            response = requests.post(url, headers=headers, data=payload)

            # ใช้ print เพื่อแสดงสถานะการตอบกลับ
            if response.status_code == 200:
                print('LINE notification sent successfully. Response:', response.text)
                return True
            else:
                print('Failed to send LINE notification. Response:', response.text)
                return False

        # สร้างข้อความแจ้งเตือนเน้นชื่อคำขอการอนุมัติ
        state_color = {
            'draft': '🔵 Draft',
            'submit': '🟡 Submitted',
            'approve': '🟢 Approved',
            'cancel': '🔴 Canceled'
        }
        colored_state = state_color.get(record.state, 'Unknown')
        approvers = record.user_ids.mapped('name')
        plain_description = record.plain_description

        if is_approved:
            message = (
                f"📄 **คำขอการอนุมัติ**: {record.name}\n"
                f"👤 **ผู้ขออนุมัติ**: {record.request_by.name}\n"
                f"🔍 **รายละเอียด**: {plain_description}\n"
                f"✅ **ผู้อนุมัติ**: {', '.join(approvers)}\n"
                f"⚙️ **สถานะ**: {colored_state}\n"
                f"👤 **ผู้อนุมัติสุดท้าย**: {self.env.user.name}\n"
            )
        else:
            message = (
                f"📄 **คำขอการอนุมัติ**: {record.name}\n"
                f"👤 **ผู้ขออนุมัติ**: {record.request_by.name}\n"
                f"🔍 **รายละเอียด**: {plain_description}\n"
                f"✅ **ผู้อนุมัติ**: {', '.join(approvers)}\n"
                f"⚙️ **สถานะ**: {colored_state}\n"
                f"❌ **ให้ปรับแก้ไขโดย**: {self.env.user.name}\n"
            )

        # ส่งแจ้งเตือนไปยังผู้ที่ขอการอนุมัติ
        request_by_user = record.request_by
        if request_by_user and request_by_user.line_token:
            send_notify(request_by_user.line_token, message)
