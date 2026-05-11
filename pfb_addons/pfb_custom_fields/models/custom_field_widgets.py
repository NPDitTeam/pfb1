# -*- coding: utf-8 -*-
from odoo import models, fields


class CustomFieldWidgets(models.Model):
    """ We can't filter a selection field dynamically so when we select a field
        its widgets also need to change according to the selected field type,
        we can't do it by a 'selection' field, need a 'Many2one' field.
    """
    _name = 'custom.field.widgets'
    _rec_name = 'description'
    _description = 'Field Widgets'

    name = fields.Char(
                string="Name", 
                help="Enter the name"
            )
    description = fields.Char(
                string="Description",                  
                help="Enter the description of field"
            )
