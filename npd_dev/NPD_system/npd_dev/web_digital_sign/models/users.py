from odoo import models, fields

class Users(models.Model):
    _inherit = "res.users"

    digital_signature = fields.Binary(string="Signature")
    line_token = fields.Char(string="Line Token")
    is_active = fields.Boolean(string="Approver Show")
    force_date_readonly = fields.Boolean(string="Force Date Readonly")
    partner_ageing_show = fields.Boolean(string="Show Partner Ageing")
