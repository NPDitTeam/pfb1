# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)

# _table สั้นไว้เพราะชื่อโมดูลยาว ทำให้ table name ที่ Odoo คำนวณจาก _name เกินลิมิต 63 ตัวอักษรของ Postgres


class ReportBilling(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_steeltech_new_qweb.report_bill_acceptance_sup'
    _table = 'report_stn_bill_acceptance_sup'
    _description = 'Report Bill Acceptance'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_npd_accounting_steeltech_new_qweb.report_bill_acceptance_sup')
        records = self.env['account.billing'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportBilling2(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_steeltech_new_qweb.report_bill_acceptance_cus'
    _table = 'report_stn_bill_acceptance_cus'
    _description = 'Report Bill Acceptance'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_npd_accounting_steeltech_new_qweb.report_bill_acceptance_cus')
        records = self.env['account.billing'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }
