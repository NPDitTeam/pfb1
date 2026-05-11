# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class ReportTaxInvoice(models.AbstractModel):
    _name = 'report.pfb_std_accounting_qweb.report_tax_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_std_accounting_qweb.report_tax_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportDebitInvoice(models.AbstractModel):
    _name = 'report.pfb_std_accounting_qweb.report_debit_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_std_accounting_qweb.report_debit_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportCreditInvoice(models.AbstractModel):
    _name = 'report.pfb_std_accounting_qweb.report_credit_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_std_accounting_qweb.report_credit_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportNonTaxInvoice(models.AbstractModel):
    _name = 'report.pfb_std_accounting_qweb.report_non_vat_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_std_accounting_qweb.report_non_vat_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptTaxInvoice(models.AbstractModel):
    _name = 'report.pfb_std_accounting_qweb.report_receipt_tax_invoice'
    _description = 'Report Receipt Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_std_accounting_qweb.report_receipt_tax_invoice')
        records = self.env['account.payment'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptTaxInvoice2(models.AbstractModel):
    _name = 'report.pfb_std_accounting_qweb.report_receipt_tax_invoice2'
    _description = 'Report Receipt Invoice2'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_std_accounting_qweb.report_receipt_tax_invoice2')
        records = self.env['account.payment'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptVoucherInvoice(models.AbstractModel):
    _name = 'report.pfb_std_accounting_qweb.report_receipt_voucher_invoice'
    _description = 'Report Receipt Voucher Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_std_accounting_qweb.report_receipt_voucher_invoice')
        records = self.env['account.voucher'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }
