# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class ReportPurchaseRequest(models.AbstractModel):
    _name = 'report.pfb_npd_pr_qweb.report_pr'
    _description = 'Report Purchase Request'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_pr_qweb.report_pr')
        records = self.env['purchase.request'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }

