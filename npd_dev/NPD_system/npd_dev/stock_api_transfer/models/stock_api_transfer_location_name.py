from odoo import models, fields, api

class StockAPITransferLocationName(models.Model):
    _name = "stock.api.transfer.location.name"
    _description = "ชื่อคลังจาก API"

    name = fields.Char(string="ชื่อคลัง", required=True)
    active_in_db = fields.Char(string='จากฐานข้อมูล')
    is_visible_in_ui = fields.Boolean(string='แสดงใน UI', default=False)

    # ✅ Field แสดงชื่อย่อ
    short_name = fields.Char(string='ชื่อคลัง (ย่อ)', compute='_compute_short_name', store=True)

    @api.depends('name')
    def _compute_short_name(self):
        for rec in self:
            if rec.name and '/' in rec.name:
                rec.short_name = rec.name.split('/')[-1]
            else:
                rec.short_name = rec.name
