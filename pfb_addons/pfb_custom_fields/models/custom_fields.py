# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import xml.etree.ElementTree as ET
import json

import logging
_logger = logging.getLogger(__name__)


class CustomFields(models.Model):
    _name = 'custom.fields'
    _rec_name = 'field_description'
    _description = 'Custom Fields'
    _inherit = 'ir.model.fields'

    @api.model
    def get_possible_field_types(self):
        """Return all available field types other than 'One2many' and
        'reference' fields."""
        field_list = sorted((key, key) for key in fields.MetaField.by_type)
        field_list.remove(('one2many', 'one2many'))
        field_list.remove(('reference', 'reference'))
        return field_list

    custom_field_id = fields.Many2one(
                'ir.model.fields', 
                string='Field Name',
                ondelete='cascade',
                help='Please Enter the name of field'
            )
    position = fields.Selection(
                [('before', 'Before'), ('after', 'After')],
                string='Position', 
                help='Select the position of custom field '
                'relative to reference field'
            )
    model_id = fields.Many2one(
                'ir.model', 
                string='Model', 
                required=True,
                index=True,
                ondelete='cascade',
                help="Mention the model name for this field "
                "to be added"
            )
    ref_model_id = fields.Many2one(
                'ir.model',
                string='Reference Model',
                help='Choose the model id for which we want '
                'to add field',
                index=True, 
            )
    selection_field = fields.Char(
                string="Selection Options",
                help='Enter the selection options'
            )
    field_type = fields.Selection(
                selection='get_possible_field_types',
                string='Field Type', 
                help='Select the field type here'
            )
    ttype = fields.Selection(
                string="Field Type",
                related='field_type',
                help='Select the field type here'
            )
    widget_id = fields.Many2one(
                'custom.field.widgets',
                string='Widget',
                help='Choose the field widget'
            )
    groups = fields.Many2many(
                'res.groups', 
                'employee_custom_fields_group_rel',
                'field_id', 
                'group_id', 
                string='Group',
                help='Enter the group for which this field is'
                ' visible'
            )
    is_extra_features = fields.Boolean(
                string="Show Extra Properties",
                help='Please enable this field for extra'
                ' attributes'
            )
    status = fields.Selection([
            ('draft', 'Draft'), 
            ('field_setup', 'Field Setup'),
            ('field_created', 'Field Created'),
            ('form', 'Added in From View'),
            ('tree', 'Added in Tree View'),
        ], 
        string='Status',
        index=True, 
        readonly=True, 
        tracking=True,
        copy=False, 
        default='draft',
        help='The status of custom field creation'
    )
    form_view_id = fields.Many2one(
                'ir.ui.view', 
                string="Form View ID",
                help='Enter the form view id'
            )
    form_view_inherit = fields.Char(
                string="Form View Inherit Id",
                related='form_view_id.xml_id',
                help='Enter the inherited form view id'
            )
    custom_form_view_id = fields.Many2one(
                'ir.ui.view',
                string="Form View ID",
                help='Enter the custom form view id'
            )
    is_field_in_form = fields.Boolean(
                string="Add Field to the Form View",
                help='Enable for form view'
            )
    is_field_in_tree = fields.Boolean(
                string="Add Field to the Tree View",
                help='Enable for tree view'
            )
    tree_view_id = fields.Many2one(
                'ir.ui.view',
                string="Tree View ID",
                help='Enter the tree view id',
            )
    tree_view_inherit = fields.Char(
                string="Tree View Inherit Id",
                related='tree_view_id.xml_id',
                help='Enter the inherited tree view id'
            )
    custom_tree_view_id = fields.Many2one(
                'ir.ui.view',
                string="Tree View ID",
                help='Enter the custom tree view id'
            )

    custom_field_id_tree = fields.Many2one(
                        'ir.model.fields', 
                        string='Field Name (Tree)',
                        ondelete='cascade',
                        help='Please Enter the name of field',
                    )
    tree_position = fields.Selection(
                [('before', 'Before'), ('after', 'After')],
                string='Tree view Position', 
                help='Select the position of custom field '
                'relative to reference field'
            )
    field_color = fields.Char(
                string="Field color"
            )
    field_bold = fields.Boolean(
                string="Bold"
            )
    field_italic = fields.Boolean(
                string="Italic"
            )
    default_style = fields.Boolean(
                default=True
            )
    is_add_to_form = fields.Boolean(
                default=False
            )
    is_add_to_tree = fields.Boolean(
                default=False
            )

    def write(self, vals):
        res = super(CustomFields, self).write(vals)
        if self.custom_field_id:
            model_fields = self.env['ir.model.fields'].search([
                    ('name', '=', self.name),
                ])
            if 'field_description' in vals:
                model_fields.write({
                        'field_description': vals['field_description']
                    })
            if 'required' in vals:
                model_fields.write({
                        'required': vals['required']
                    })
            if 'readonly' in vals:
                model_fields.write({
                        'readonly': vals['readonly']
                    })
        return res

    def submit_field_to_setup(self):
        for rec in self:
            rec.status = 'field_setup'

    @api.onchange('is_field_in_form')
    def _onchange_is_field_in_form(self):
        """Return the corresponding form, tree view id and field records"""
        form_view_ids = self.model_id.view_ids.filtered(
            lambda l: l.type == 'form' and l.mode == 'primary')
        field_records = self.env['ir.model.fields'].sudo().search([
            ('model', '=', self.model_id.model)])
        field_list = [field.id for rec in field_records for field in rec]
        return {'domain': {
            'form_view_id': [('id', 'in', form_view_ids.ids)],
            'custom_field_id': [('id', 'in', field_list)]
        }}

    @api.onchange('is_field_in_tree')
    def _onchange_is_field_in_tree(self):
        tree_view_ids = self.model_id.view_ids.filtered(
            lambda l: l.type == 'tree' and l.mode == 'primary')
        field_records = self.env['ir.model.fields'].sudo().search([
            ('model', '=', self.model_id.model)])
        field_list_tree = []
        if tree_view_ids:
            for tree_view in tree_view_ids:
                arch = tree_view.arch
                tree = ET.fromstring(arch)  # Replace with your actual XML string
                field_names_tree_view = []
                for node in tree.findall('.//field'):  # Find all <field> elements
                    field_names_tree_view.append(node.get('name'))
                for field in field_records:
                    if field.name in field_names_tree_view:
                        field_list_tree.append(field.id)

        return {'domain': {
            'tree_view_id': [('id', 'in', tree_view_ids.ids)],
            'custom_field_id_tree': [('id', 'in', field_list_tree)]
        }}

    @api.onchange('field_type')
    def _onchange_field_type(self):
        """When changing field type, this method returns widget of
        corresponding field type"""
        widget_mapping = {
            'binary': [('name', '=', 'image')],
            'many2many': [('name', 'in', ['many2many_tags', 'binary'])],
            'selection': [('name', 'in', ['radio', 'priority'])],
            'float': [('name', '=', 'monetary')],
            'many2one': [('name', '=', 'selection')],
        }
        return {'domain': {'widget': widget_mapping.get(self.field_type,
                                                        [('id', '=', False)])}}

    def action_create_custom_fields(self):
        """ The 'CREATE FIELD' button method is used to add new field to form
         view of required model"""
        self.write({'status': 'field_created'})
        if self.field_type == 'monetary' and not self.env[
            'ir.model.fields'].sudo().search([('model', '=', self.model_id.id),
                                              ('name', '=', 'currency_id')]):
            self.env['ir.model.fields'].sudo().create({
                'name': 'x_currency_id',
                'field_description': 'Currency',
                'model_id': self.model_id.id,
                'ttype': 'many2one',
                'relation': 'res.currency',
                'is_custom_field': True
            })
        self.env['ir.model.fields'].sudo().create({
            'name': self.name,
            'field_description': self.field_description,
            'model_id': self.model_id.id,
            'ttype': self.field_type,
            'relation': self.ref_model_id.model,
            'required': self.required,
            'index': self.index,
            'store': self.store,
            'help': self.help,
            'readonly': self.readonly,
            'selection': self.selection_field,
            'copied': self.copied,
            'is_custom_field': True
        })

        if self.model_id.model == 'hr.department':
            try:
                model_name = str(self.model_id.model)
                self.env[model_name].action_upgrade_method()
            except:
                pass

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_add_field_to_form_view(self):
        inherit_form_view_name = str(
            self.form_view_id.name) + ".inherit.custom." + str(
            self.field_description) + ".field"
        xml_id = self.form_view_id.xml_id
        inherit_id = self.env.ref(xml_id)
        arch_base = _('<?xml version="1.0"?>'
                      '<data>'
                      '<field name="%s" position="%s">'
                      '<field name="%s"/>'
                      '</field>'
                      '</data>') % (self.custom_field_id.name,
                                    self.position, self.name)
        if self.widget_id:
            arch_base = _('<?xml version="1.0"?>'
                          '<data>'
                          '<field name="%s" position="%s">'
                          '<field name="%s" widget="%s"/>'
                          '</field>'
                          '</data>') % (self.custom_field_id.name,
                                        self.position, self.name,
                                        self.widget_id.name)
        self.custom_form_view_id = self.env['ir.ui.view'].sudo().create({
            'name': inherit_form_view_name,
            'type': 'form',
            'model': self.model_id.model,
            'mode': 'extension',
            'inherit_id': inherit_id.id,
            'arch_base': arch_base,
            'active': True
        })
        self.update_field_color()
        self.write({
                'status': 'form',
                'is_add_to_form': True
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_add_field_to_tree_view(self):
        """ Button 'Add to Tree View' is used add the created custom field to
        tree view of corresponding model"""
        tree_view = self.env['ir.ui.view'].search(
            [('model', '=', self.model_id.model), ('type', '=', 'tree')])
        view_id_tree = self.env.ref(self.tree_view_inherit)
        if tree_view and view_id_tree.arch:
            if self.is_field_in_tree:
                inherit_tree_view_name = str(
                    self.tree_view_id.name) + ".inherit.custom" + \
                                         str(self.field_description) + ".field"
                tree_view_arch_base = _(
                    '<?xml version="1.0"?>'
                    '<data>'
                    '''<xpath expr="//tree/field[@name='%s']" position="%s">'''
                    '''<field name="%s" optional="show"/>'''
                    '''</xpath>'''
                    '''</data>''') % (self.custom_field_id_tree.name, self.tree_position ,self.name)
                self.custom_tree_view_id = self.env['ir.ui.view'].sudo().create(
                    {'name': inherit_tree_view_name,
                     'type': 'tree',
                     'model': self.model_id.model,
                     'mode': 'extension',
                     'inherit_id': self.tree_view_id.id,
                     'arch_base': tree_view_arch_base,
                     'active': True})
                self.write({
                        'status': 'tree',
                        'is_add_to_tree': True
                    })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
        else:
            raise ValidationError(
                _('Error! Selected Model You cannot add a custom field to the '
                  'tree view.'))

    # @api.depends('model_id')
    # @api.onchange('model_id')
    # def onchange_domain(self):
    #     """Return the fields that currently present in the form"""
    #     form_view_ids = self.model_id.view_ids.filtered(
    #         lambda l: l.type == 'form' and l.mode == 'primary')
    #     tree_view_ids = self.model_id.view_ids.filtered(
    #         lambda l: l.type == 'tree' and l.mode == 'primary')
    #     field_records = self.env['ir.model.fields'].sudo().search([
    #         ('model', '=', self.model_id.model)])
    #     field_list = [field.id for record in field_records for field in record]
    #     return {'domain': {
    #         'form_view_id': [('id', 'in', form_view_ids.ids)],
    #         'tree_view_id': [('id', 'in', tree_view_ids.ids)],
    #         'position_field': [('id', 'in', field_list)]
    #     }}

    @api.depends('field_type')
    @api.onchange('field_type')
    def onchange_field_type(self):
        """"Onchange method of field_type, when changing field type it will
        return domain for widget """
        widget_mappings = {
            'binary': [('name', '=', 'image')],
            'many2many': [('name', 'in', ['many2many_tags', 'binary'])],
            'selection': [('name', 'in', ['radio', 'priority'])],
            'float': [('name', '=', 'monetary')],
            'many2one': [('name', '=', 'selection')],
        }
        return {'domain': {'widget': widget_mappings.get(self.field_type,
                                                         [('id', '=', False)])}}

    def unlink(self):
        """ Unlinking method of field"""
        # if self.form_view_id:
        #     self.form_view_id.active = False
        # if self.tree_view_id:
        #     self.tree_view_id.active = False
        result = super().unlink()
        return result

    def update_field_color(self):
        if self.custom_form_view_id:
            form_view_id = self.custom_form_view_id
            arch = form_view_id.arch
            form = ET.fromstring(arch)  # Replace with your actual XML string
            field_name_xpath = './/field[@name="%s"]' % (self.name)
            for node in form.findall(field_name_xpath):  # Find all <field> elements
                field_style = ''
                if self.field_color:
                    field_style += 'color: %s;' % (self.field_color)
                if self.field_bold:
                    field_style += 'font-weight: bold;'
                if self.field_italic:
                    field_style += 'font-style: italic;'
                node.set('style', field_style)
            updated_form = ET.tostring(form, encoding="unicode")
            form_view_id.write({
                    'arch': updated_form,
                    'arch_db': updated_form
                })
            self.default_style = False
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def reset_to_default_style(self):
        self.write({
                'field_color': '',
                'field_bold': False,
                'field_italic': False,
            })
        self.update_field_color()
        self.default_style = True
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_remove_field_from_form_view(self):
        if self.custom_form_view_id:
            form_view_obj = self.env['ir.ui.view'].search([
                    ('id', '=', self.custom_form_view_id.id)
                ])
            try:
                form_view_obj.sudo().unlink()
            except:
                raise ValidationError(
                    _('Unable to remove field'))

            status = 'field_created'
            if self.custom_tree_view_id:
                status = 'tree'
            self.write({
                    'is_field_in_form': False,
                    'status': status,
                    'custom_field_id': None,
                    'position': None,
                    'form_view_id': None,
                    'form_view_inherit': '',
                    'custom_form_view_id': None,
                    'is_add_to_form': False
                })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def action_remove_field_from_tree_view(self):
        """ Button 'Remove From Tree View' is used remove the created field to
        tree view of corresponding model"""
        if self.custom_tree_view_id:
            tree_view_obj = self.env['ir.ui.view'].search([
                    ('id', '=', self.custom_tree_view_id.id)
                ])
            try:
                tree_view_obj.sudo().unlink()
            except:
                raise ValidationError(
                    _('Unable to remove field'))

            status = 'field_created'
            if self.custom_form_view_id:
                status = 'form'

            self.write({
                    'is_field_in_tree': False,
                    'status': status,
                    'tree_view_id': None,
                    'tree_view_inherit': '',
                    'custom_tree_view_id': None,
                    'tree_position': None,
                    'custom_field_id_tree': None,
                    'is_add_to_tree': False
                })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
