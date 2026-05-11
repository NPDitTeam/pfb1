from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    branch_ids = fields.Many2many(
        comodel_name='res.branch',  # อิงตามฟิลด์เดิม
        string='เลือกเพิ่มเติม',
        help='เลือกสาขาเพิ่มเติมได้มากกว่า 1 รายการ'
    )
