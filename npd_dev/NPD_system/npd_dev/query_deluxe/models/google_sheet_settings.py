# models/google_sheet_settings.py

from odoo import models, fields

class GoogleSheetSettings(models.Model):
    _name = 'google.sheet.settings'
    _description = 'Google Sheet Settings'

    name = fields.Char(string='Name')
    email = fields.Char(string='Email')
    json_file = fields.Binary(string='JSON File')
