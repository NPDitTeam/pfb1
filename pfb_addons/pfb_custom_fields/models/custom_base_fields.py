# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import xml.etree.ElementTree as ET
import json

import logging
_logger = logging.getLogger(__name__)


class CustomBaseFields(models.Model):
    _name = 'custom.base.fields'
    _description = 'Custom Base Fields'

    model_id = fields.Many2one(
                'ir.model', 
                string='Model', 
                required=True,
                index=True,
                ondelete='cascade',
                help="Mention the model name for this field "
                "to be added"
            )
    custom_field_id = fields.Many2one(
                'ir.model.fields', 
                string='Field Name',
                required=True,
                ondelete='cascade',
                help='Please Enter the name of field'
            )
    field_description = fields.Char(
                string="New Label",
                required=True
            )

    @api.onchange('model_id')
    def onchange_domain(self):
        """Return the fields that currently present in the form"""
        custom_field_ids = self.env['ir.model.fields'].search([
                ('model_id', '=', self.model_id.id)
            ])
        field_list = []
        for field in custom_field_ids:
            field_list.append(field.id)
        return {'domain': {
            'custom_field_id': [('id', 'in', field_list)],
        }}


    # @api.model
    # def create(self, vals):
    #     res = super(CustomBaseFields, self).create(vals)
    #     _logger.info(res.custom_field_id.id)
    #     _logger.info('------------')
    #     source_field = self.env['ir.model.fields'].search({
    #             'id', '=', self.custom_field_id.id
    #         })
    #     source_field.field_description = self.field_description
    #     return res

