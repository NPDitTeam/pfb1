# -*- coding: utf-8 -*-


from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)

class ReportTaxInvoiceBase(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.amount_to_text_base'
    _description = 'Base class for amount to text conversion'

    def convert_amount_to_text(self, amount):
        amount = float(f"{amount:.2f}")
        baht, satang = divmod(amount, 1)
        baht_text = self.read_number(int(baht))
        satang_text = self.read_number(int(round(satang * 100)))

        result = f"{baht_text}บาท"
        if satang_text:
            result += f"{satang_text}สตางค์"
        else:
            result += "ถ้วน"
        return result

    def read_number(self, number):
        position_call = ["แสน", "หมื่น", "พัน", "ร้อย", "สิบ", ""]
        number_call = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]

        result = ""
        if number == 0:
            return result

        if number >= 1_000_000:
            result += self.read_number(number // 1_000_000) + "ล้าน"
            number %= 1_000_000

        divider = 100_000
        for pos, call in enumerate(position_call):
            digit = number // divider
            if divider == 10 and digit == 2:
                result += "ยี่"
            elif divider == 10 and digit == 1:
                result += ""
            elif divider == 1 and digit == 1 and result:
                result += "เอ็ด"
            else:
                result += number_call[digit]
            result += call if digit else ""
            number %= divider
            divider //= 10
        return result


class ReportTaxInvoice(models.AbstractModel):
    _inherit = 'report.pfb_npd_accounting_qweb.amount_to_text_base'
    _name = 'report.pfb_npd_accounting_qweb.report_tax_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_accounting_qweb.report_tax_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,
            'convert_amount_to_text': self.convert_amount_to_text,  # เพิ่มฟังก์ชันนี้ใน context
        }


class ReportDebitInvoice(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_debit_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_accounting_qweb.report_debit_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportCreditInvoice(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_credit_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_accounting_qweb.report_credit_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportNonTaxInvoice(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_non_vat_invoice'
    _description = 'Report Tax Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_accounting_qweb.report_non_vat_invoice')
        records = self.env['account.move'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptTaxInvoice(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_receipt_tax_invoice'
    _description = 'Report Receipt Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_npd_accounting_qweb.report_receipt_tax_invoice')
        records = self.env['account.payment'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportNoReceipt(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_no_receipt_invoice'
    _description = 'Report No Receipt Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_npd_accounting_qweb.report_no_receipt_invoice')
        records = self.env['account.payment'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptTaxInvoice2(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_receipt_tax_invoice2'
    _description = 'Report Receipt Invoice2'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_npd_accounting_qweb.report_receipt_tax_invoice2')
        records = self.env['account.voucher'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }


class ReportReceiptTaxInvoice3(models.AbstractModel):
    _name = 'report.pfb_npd_accounting_qweb.report_receipt_tax_invoice3'
    _description = 'Report Receipt Invoice3'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'pfb_npd_accounting_qweb.report_receipt_tax_invoice3')
        records = self.env['account.voucher'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }        
