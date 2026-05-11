# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import file_open
import logging
_logger = logging.getLogger(__name__)
MIMETYPE = ['application/octet-stream', 'image/svg+xml']
class ReportsDesignerExportWizard(models.TransientModel):
    _name = 'reports_designer_export_wizard'
    _description = "reports_designer_export Wizard"
    multiple_export = fields.Boolean(string='Multiple Export of Configurations to a ZIP archive',
                                     default=False)        
    def export_excel(self):
        """
        """
        active_ids = self.env.context.get('active_ids', [])
        datas = {'ids': active_ids}
        datas['active_model'] = self.env.context.get('active_model')
        datas['multiple_export'] = self.multiple_export
        return self.env['reports_designer_export_gen'].create_conf(datas)
    def wizard_view(self):
        return {'name': _('Report Export'),
                'view_mode': 'kanban,tree,form',
                'view_id': False,
                'res_model': 'reports_designer_export_wizard',
                'src_model': 'reports.designer',
                'type': 'ir.actions.act_window',
                'target': 'new',
                }
class ReportsDesignerImportWizard(models.TransientModel):
    _name = 'reports_designer_import_wizard'
    _description = "reports_designer_import Wizard"
    data = fields.Binary(
                        string='Import Report Configuration', 
                        required=True, 
                        help='Get you file a report configuration.'
                        )
    def wizard_view(self):
        return {'name': _('Report Import'),
                'view_mode': 'kanban,tree,form',
                'view_id': False,
                'res_model': 'reports_designer_import_wizard',
                'src_model': 'reports.designer',
                'type': 'ir.actions.act_window',
                'target': 'new',
                }
    def import_excel(self):
        """
        """
        datafile = self.env['ir.attachment'].sudo().search_read([
            ('res_model', '=', 'reports_designer_import_wizard'), 
            ('res_id', '=', self.id), 
            ('res_field', '=', 'data')],
            []
            )
        if datafile:
            config = self._get_template(datafile[0]['id']) or {}
            config_fp = config._full_path(config['store_fname'])
            if not config.mimetype in MIMETYPE:      
                msg = ('Does not support the file format, '
                       'please use correct file format.')
                raise UserError(msg)        
            with open(config_fp, 'rb') as fp:
                try:
                    tools.convert.convert_xml_import(self._cr, 'reports_designer', fp, {}, 'init', False)
                except:
                    raise UserError(
'''Parse Error! Can't load Incorrect file. Please use correct file format,
or
In the database into which you import the report configuration, all modules on which the report depends must be installed and all custom fields (if you created such through the user interface) on which the report depends must also be created.
You can view the modules on which the report depends by opening the Report Configuration File in the "Module Dependencies" section.
Please check if these modules are installed in your database to which you want to import the report?                       
'''                       
                       )
    @api.model
    @api.returns('ir.attachment', lambda value: value.id)
    def _get_template(self, template_id):
        return self.env['ir.attachment'].sudo().search([('res_model', '=', 'reports_designer_import_wizard'), ('id', '=', template_id)])
