# -*- coding: utf-8 -*-

from odoo import api, models,tools, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class CashReceiptForm(models.AbstractModel):
    _name = 'report.pfb_std_voucher_qweb.cash_receipt_pdf_report_pdf'


    def year_convert(self, convert_date):
        date_converted = convert_date + relativedelta(years=543)
        date_converted = date_converted.strftime('%d/%m/%Y')
        return date_converted

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.voucher'].browse(docids)
        thaibahttext = ''
        sum_total = 0
        sum_tt = 0
        check_if = 0
        group = []
        #for doc in docs:
            #if doc.amount_cash != 0:
                #check_if = 1
            #elif doc.cheque_ids:
                #check_if = 2
            #elif doc.banktr_ids:
                #check_if = 3
            #else:
                #check_if = 0
            #print(check_if)
            #for line in doc.line_ids:
                #group.append(line)
                #sum_total += line.amount_receipt
        #sum_tt = sum_total
        #thaibahttext = bahttext(sum_total)
        return {
            'doc_ids': docs.ids,
            'doc_model': 'account.voucher',
            'docs': docs,
            'thaibahttext': thaibahttext,
            'check_if': check_if,
            'group': group,
        }        
class AccountAdvanceForm(models.AbstractModel):
    _name = 'report.pfb_std_voucher_qweb.account_advance_clear_report_pdf'

    def year_convert(self, convert_date):
        date_converted = convert_date + relativedelta(years=543)
        date_converted = date_converted.strftime('%d/%m/%Y')
        return date_converted

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.advance.clear'].browse(docids)
        thaibahttext = ''
        check_if = 0
        sum_amount = 0
        bank_cash = ''
        return {
            'doc_ids': docs.ids,
            'doc_model': 'account.advance.clear',
            'docs': docs,
            'thaibahttext': thaibahttext,
            'check_if': check_if,
        }


class AccountAdvanceForm2(models.AbstractModel):
    _name = 'report.pfb_std_voucher_qweb.account_advance_clear_report_pdf2'


    def year_convert(self, convert_date):
        date_converted = convert_date + relativedelta(years=543)
        date_converted = date_converted.strftime('%d/%m/%Y')
        return date_converted

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.advance.clear'].browse(docids)
        thaibahttext = ''
        check_if = 0
        sum_amount = 0
        bank_cash = ''
        return {
            'doc_ids': docs.ids,
            'doc_model': 'account.advance.clear',
            'docs': docs,
            'thaibahttext': thaibahttext,
            'check_if': check_if,
        }
