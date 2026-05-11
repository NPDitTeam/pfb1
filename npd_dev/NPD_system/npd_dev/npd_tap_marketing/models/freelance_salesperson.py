from odoo import models, fields


class FreelanceSalesperson(models.Model):
    _name = 'freelance.salesperson'
    _description = 'เซลล์ Freelance'
    _order = 'sequence, id'

    name = fields.Char(string='ชื่อเซลล์', required=True)
    sequence = fields.Integer(string='ลำดับ', default=10)
    active = fields.Boolean(string='ใช้งาน', default=True)
