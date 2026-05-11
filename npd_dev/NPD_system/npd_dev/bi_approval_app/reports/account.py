# -*- coding: utf-8 -*-
from odoo import api, models


class ReportNonTaxInvoice(models.AbstractModel):
    _name = 'report.bi_approval_app.report_my_approval_template'
    _description = 'Report My approval'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('bi_approval_app.report_my_approval_template')
        records = self.env['approval.request'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': report.model,
            'docs': records,
            'data': data,
            'company': self.env.company,
        }
