# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class ReportBilling(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_bill_acceptance_sup'
    _description = 'Report Bill Acceptance'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_accounting_qweb.report_bill_acceptance_sup')
        records = self.env['account.billing'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportBilling2(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_bill_acceptance_cus'
    _description = 'Report Bill Acceptance'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_accounting_qweb.report_bill_acceptance_cus')
        records = self.env['account.billing'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }

