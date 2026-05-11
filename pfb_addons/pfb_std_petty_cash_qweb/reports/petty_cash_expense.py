# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class ReportPurchaseOrder(models.AbstractModel):
    _name = 'report.pfb_std_petty_cash_qweb.report_po'
    _description = 'Report Petty Cash'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_std_petty_cash_qweb.report_po')
        records = self.env['petty.cash.expense'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,
        }
