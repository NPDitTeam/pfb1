# ไฟล์ approval_name_approval_type.py
from odoo import api, fields, models, _

class ApprovalNameApprovalType(models.Model):
    _name = "approval.name_approval_type"
    _description = "Approval Name Type"

    name = fields.Char(string="Approval Type", required=True)
    description = fields.Text(string="Description")
