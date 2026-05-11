# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class ReportTaxInvoice(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_tax_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('npd_npd_accounting_qweb.report_tax_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportDebitInvoice(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_debit_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('npd_npd_accounting_qweb.report_debit_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportCreditInvoice(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_credit_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('npd_npd_accounting_qweb.report_credit_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportNonTaxInvoice(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_non_vat_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('npd_npd_accounting_qweb.report_non_vat_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptTaxInvoice(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_receipt_tax_invoice'
    _description = 'Report Receipt Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'npd_npd_accounting_qweb.report_receipt_tax_invoice')
        records = self.env['account.payment'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportNoReceipt(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_no_receipt_invoice'
    _description = 'Report No Receipt Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'npd_npd_accounting_qweb.report_no_receipt_invoice')
        records = self.env['account.payment'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptTaxInvoice2(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_receipt_tax_invoice2'
    _description = 'Report Receipt Invoice2'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'npd_npd_accounting_qweb.report_receipt_tax_invoice2')
        records = self.env['account.voucher'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }
        
class ReportReceiptTaxInvoice3(models.AbstractModel):
    _name = 'report.npd_npd_accounting_qweb.report_receipt_tax_invoice3'
    _description = 'Report Receipt Invoice3'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'npd_npd_accounting_qweb.report_receipt_tax_invoice3')
        records = self.env['account.voucher'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }        
