# -*- coding: utf-8 -*-
from odoo import models, fields


class IrModelFields(models.Model):
    """Adding a new field to understand the dynamically created fields."""
    _inherit = 'ir.model.fields'

    is_custom_field = fields.Boolean(string="Custom Field",
                                      help='Enable this field for custom field'
                                           'creation')

    def name_get(self):
        result = []
        for record in self:
            if self.env.context.get('custom_field', True):
                result.append((record.id, "{} ({}, {})".format(record.field_description, record.model_id.model, record.name)))
            else:
                result.append((record.id, "{} ({})".format(record.field_description, record.model_id.model)))
        return result

