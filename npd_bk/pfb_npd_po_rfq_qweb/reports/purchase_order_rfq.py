# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class ReportPurchaseOrder(models.AbstractModel):
    _name = 'report.pfb_npd_po_rfq_qweb.report_po'
    _description = 'Report Purchase Order'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_po_rfq_qweb.report_po')
        records = self.env['purchase.order'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }

