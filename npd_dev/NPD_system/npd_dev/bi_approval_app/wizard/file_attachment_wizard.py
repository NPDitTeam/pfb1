# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class FileAttachmnetWizard(models.TransientModel):
    _name = "file.attachment.wizard"
    _description = 'File Attachmnet Wizard'

    choose_file = fields.Binary(string="Select File")
    file_name = fields.Char(string="FileName")

    def action_attachment(self):
        request_approve_ids = self.env['approval.request'].browse(self.env.context['active_ids'])
        datas = self.choose_file
        attachment_file_vals = {
                'name': self.file_name,
                'datas': datas,
                'type': 'binary',
                'res_model': 'approval.request',
                'res_id': request_approve_ids.id,
            }
        self.env['ir.attachment'].create(attachment_file_vals)
