from odoo import fields, models, api

class AssetCategory(models.Model):
    _name = "asset.category"
    _description = "ประเภททรัพย์สิน"

    name = fields.Char(string="ชื่อประเภททรัพย์สิน")
# class AssetCategory(models.Model):
#     _name = "asset.category"
#     _description = "Asset Category"
#
#     name = fields.Char(string="Name")