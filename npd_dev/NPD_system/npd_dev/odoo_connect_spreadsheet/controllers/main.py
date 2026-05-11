# -*- coding: utf-8 -*-
from odoo.addons.web.controllers.main import DataSet

from odoo import http
from odoo.http import request


class DataSetInherit(DataSet):
    @http.route(['/web/dataset/call_kw', '/web/dataset/call_kw/<path:path>'], type='json', auth="user")
    def call_kw(self, model, method, args, kwargs, path=None):
        res = super(DataSetInherit, self).call_kw(model, method, args, kwargs, path=None)
        for spreadsheet in request.env['connect.spreadsheet'].search([('state', '=', 'active')]):
            if spreadsheet.update_type == 'realtime' and spreadsheet.model_id.model == model \
                    and method in ['create', 'write', 'unlink']:
                spreadsheet.sync_spreadsheet()
        return res

    @http.route('/web/dataset/call_button', type='json', auth="user")
    def call_button(self, model, method, args, kwargs):
        res = super(DataSetInherit, self).call_button(model, method, args, kwargs)
        for spreadsheet in request.env['connect.spreadsheet'].search([('state', '=', 'active')]):
            if spreadsheet.update_type == 'realtime' and spreadsheet.model_id.model == model:
                spreadsheet.sync_spreadsheet()
        return res
