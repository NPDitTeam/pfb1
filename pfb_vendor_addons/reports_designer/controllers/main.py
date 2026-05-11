# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import _serialize_exception
from odoo.tools import html_escape
import json
SUPPORTED_FORMATS = ('xlsx', 'xlsm', 'conf','zip',)
class ReportsDesignerController(http.Controller):
    @http.route(['/reports_designer',
                 '/reports_designer/<int:id>',
                 '/reports_designer/<int:id>/<string:filename>',
                 '/reports_designer_export',
                 '/reports_designer_export/<int:id>',
                 '/reports_designer_export/<int:id>/<string:filename>'], type='http', auth='user')
    def reports_designer(self, id=None, model='ir.attachment', output_format='xlsx', report_name=None, token=None, report_id=None, filename=None, download=None, **kw):
        uid = request.session.uid
        domain = [('id', '=', id),('create_uid', '=', uid)]
        context_id = request.env[model].sudo().search(domain, limit=1)
        attach_fpath = ''
        attach_fname = ''
        if context_id: 
            attach_fname = context_id['name']
            store_fname = context_id['store_fname']
            attach_fpath = context_id._full_path(store_fname)
        filename = attach_fname if not filename else filename
        filename_attachment = 'attachment; filename=' + filename + ';'
        filename_attachment = filename_attachment.encode('utf-8')
        try:
            with open(attach_fpath, "rb") as f:
                content = f.read()
                f.close()
            if ".".join(filename.split('.')[-1:]) in SUPPORTED_FORMATS:
                response = request.make_response(
                    content,
                    headers=[
                        ('Content-Type', 'application/vnd.ms-excel'),
                        ('Content-Disposition', filename_attachment),
                        ('Content-Length', len(content))                        
                    ]
                )
                return response
        except Exception as e:
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': 'Odoo Server Error',
                'data': se
            }
            return request.make_response(html_escape(json.dumps(error)))
        else:
            return request.not_found()
