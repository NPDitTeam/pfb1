from odoo import api, fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    start_date = fields.Date(string='วันที่เริ่มต้นการเช่า')

    end_date = fields.Date(string='วันที่สิ้นสุดการเช่า')