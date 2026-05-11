# -*- coding: utf-8 -*-
from odoo import models, fields


class IrModel(models.Model):
    _inherit = 'ir.model'

    def name_get(self):
        result = []
        for record in self:
            if self.env.context.get('custom_field', True):
                result.append((record.id, "{} ({})".format(record.name, record.model)))
            else:
                result.append((record.id, record.name))
        return result
